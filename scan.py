#scan app. version for 16x2 displays     ------------------------------------

import cv2 # type: ignore
from pyzbar import pyzbar # type: ignore
from time import sleep
import requests
import json
import pathlib
import logging
from datetime import datetime
import pytz # type: ignore
import os
import sys
import threading
import RPi.GPIO as GPIO # type: ignore

conf = open(str(pathlib.Path().resolve()) + '/config.json')
config = json.loads(conf.read())
conf.close()

#region display ----------------------------

display_type = config['screen']['display_type']

if display_type == 'lcd.16x2':
    from Adafruit_CharLCD import Adafruit_CharLCD  # type: ignore

    cols = config['screen']['cols']
    lines = config['screen']['lines']
    rs = config['screen']['rs']
    en = config['screen']['en']
    d4 = config['screen']['d4']
    d5 = config['screen']['d5']
    d6 = config['screen']['d6']
    d7 = config['screen']['d7']
    backlight = config['screen']['backlight']

    disp = Adafruit_CharLCD(rs=rs, en=en, d4=d4, d5=d5, d6=d6, d7=d7,
                        cols=cols, lines=lines, backlight=backlight)
elif display_type == 'oled.128x32':
    from PIL import Image
    from PIL import ImageDraw
    from PIL import ImageFont
    import Adafruit_GPIO.SPI as SPI # type: ignore
    import Adafruit_SSD1306 # type: ignore
    RST = None     # on the PiOLED this pin isnt used
    # Note the following are only used with SPI:
    DC = 23
    SPI_PORT = 0
    SPI_DEVICE = 0

    # 128x32 display with hardware I2C:
    disp = Adafruit_SSD1306.SSD1306_128_32(rst=RST)

    # Initialize library.
    disp.begin()

    # Clear display.
    disp.clear()
    disp.display()

    width = disp.width
    height = disp.height
    image = Image.new('1', (width, height))

    font = ImageFont.load_default()

    # Get drawing object to draw on image.
    draw = ImageDraw.Draw(image)

    # Draw a black filled box to clear the image.
    draw.rectangle((0,0,width,height), outline=0, fill=0)

    
#endregion display -------------------

#----- logger section -----
logging.basicConfig(filename='history.log', level=logging.ERROR, 
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger(__name__)

#region ---- variables section  -------------

code = ''
code_hide = ''
settingsMode = False
readyToConfig = False
code_hide_mark = config['screen']['code_hide_mark']
show_code = config['app']['show_code']
debugging = config['app']['debugging']
pwdRST = config['app']['pwdRST']
_settingsCode = config['app']['settingsCode']
tzone = config['app']['timezone']

screen_saver = 0
version_app = config['app']['version']
#api ------
url = config['api']['url']
api_valid_code = config['api']['api_valid_code']
api_codes_events = config['api']['api_codes_events']
usr = config['api']['usr']
namePlace = config['app']['NamePlace']
password = config['app']['pwd']
buzzer_pin = config['pi_pins']['buzzer']


#decode and code verification
acc = 0
acc_code = 0
first_code = ''
last_capture = datetime.now()

#endregion


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(buzzer_pin,GPIO.OUT)
buzzer = GPIO.PWM(buzzer_pin, 1000)

# region ------------- Key pad gpio setup  ----------------------------
KEY_UP = 0 
KEY_DOWN = 1

MATRIX = config['keypad_matrix'][config['keypad_matrix']['default']]
ROWS = config['pi_pins']['keypad_rows']
COLS = config['pi_pins']['keypad_cols']

for pin in ROWS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.HIGH)

for pin in COLS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# endregion -----------------------------------------

def initial():
    showVersion('ver. ' + version_app)

def showVersion(msg):
    showMsg(msg + '.')
    sleep(0.9)

    showMsg(msg + '..')
    sleep(0.9)

    showMsg(msg + '...')
    sleep(0.9)

    showMsg(msg + '....')
    sleep(3)

def clear():
    if display_type == 'oled.128x32':
        draw.rectangle((0,0,width,height), outline=0, fill=0)
        disp.image(image)
        disp.display()
    elif display_type == 'lcd.16x2':
        disp.clear()

def showMsg(msg1='',msg2=''):
    if display_type == 'lcd.16x2':
        clear()
        msg=''
        if (msg1 == 'headerControl'):
            msg1 = '* <-     # enter' 
            msg = f"{msg1:^16}" + '\n' + f"{msg2:^16}"
        else:
            msg = f"{msg1:^16}" + '\n' + f"{msg2:^16}"

        disp.message(msg)
    elif display_type == 'oled.128x32':
        draw.rectangle((0,0,width,height), outline=0, fill=0)
        if (msg1 != ''):
            if (msg1 == 'headerControl'):
                space = 50 - 11 # 50 = screen length considering the font, 11 = '* <-# enter'
                draw.text((0, 2),f"{'* <-':<{space}}# enter", font=font, fill=255)
            else:
                draw.text((0, 2),f"{msg1:^50}", font=font, fill=255)

        if (msg2 != ''):
            draw.text((0, 16),f"{msg2:^40}", font=font, fill=255)
        
        disp.image(image)
        disp.display()



def restart():
    showMsg('Reiniciando..')
    cap.release()
    cv2.destroyAllWindows()
    os.execl(sys.executable, sys.executable, *sys.argv)

# region -------- Configuration  -------------------------------------

def changeSetting(value):
    global MATRIX
    global sendStatus
    applied = False

    # keypad  -----------------------------------
    if value == '00': # reboot
        printHeaderSettings()
        showMsg('Booting')
        sleep(3)
        restart()
        applied = True

    elif value == '01': # get Sim Info
        # getSimInfo()
        applied = True

    elif value == '02': # get timestamp
        # updTimestamp()
        applied = True

    elif value == '03': # get phone number
        sendStatus = True
        # getPhoneNum()
        applied = True

    elif value == '1': # set matrix for flex keypad
        MATRIX = config['keypad_matrix']['flex']
        showMsg('set keypad','flex')
        applied = True

    elif value == '2': # set matrix for hard plastic keypad
        MATRIX = config['keypad_matrix']['hardPlastic']
        showMsg('set keypad','hard plastic')
        applied = True

    # debug -----------------------------------
    elif value == '10':  #debug true
        # jsonTools.updJson('u','config.json','app', 'debugging', True)
        applied = True

    elif value == '11': #debug false
        # jsonTools.updJson('u','config.json','app', 'debugging', False)
        applied = True

    return applied
    
# endregion

def decode_qr(frame):
    #acc increment calling value
    global acc
    global acc_code
    global first_code
    global last_capture
    global screen_saver
    diff_time = 0

    # Decodifica los códigos QR en el frame
    decoded_objects = pyzbar.decode(frame)
    for obj in decoded_objects:
        # Extraer el texto del QR
        qr_data = obj.data.decode("utf-8")
        qr_type = obj.type

        #ignore duplicate verificartion for short time readings -----
        if qr_type == 'QRCODE':
            if first_code == qr_data:
                acc_code += 1
            else:
                acc_code = 1
                first_code = qr_data

            now = datetime.now()
            diff_time = (now - last_capture).seconds
        
        #end duplicate verification     ----------------------
            acc += 1

        # Imprimir el texto del QR y el tipo en la consola
            if diff_time > 15:
                GPIO.output(buzzer_pin,GPIO.HIGH)
                sleep(0.5)
                GPIO.output(buzzer_pin,GPIO.LOW)
                
                if qr_data == password:
                    restart()
                    return
            
                screen_saver = 0
                print("{}.- Data: '{}' | Time: '{}' | Acc-code: '{}' | Diff: '{}' "
                    .format(str(acc),f"{qr_data:^6}", datetime.now(pytz.timezone(tzone)), acc_code, str(diff_time)))
                
                activeCode(qr_data)

def activeCode(code):
    global last_capture
    global namePlace
    last_capture = datetime.now()
    curl = url + api_valid_code + code + '/' + usr
    try:
        res = requests.get(curl)
        if res.status_code == 200:
            showMsg('Bienvenido')
            sleep(5)
            showMsg(namePlace)
            return True
        else:
            showMsg('Codigo','No valido')
            sleep(7)
            showMsg(namePlace)
            return False
        code = ''
    except requests.exceptions.RequestException as e:
        logger.error(e)
        return False

def screenSaver():
    global settingsMode
    global readyToConfig

    readyToConfig = False
    settingsMode = False
    clear()
    

def printHeader():
    showMsg("* <-    # enter")

def printHeaderSettings():
    showMsg( "* <-     # enter","config")

def monitor():
    global screen_saver
    while True:
        sleep(1)
        if screen_saver <= 60:
            screen_saver += 1
        else:
            screenSaver()

def PollKeypad():
    global ROWS
    global COLS
    global screen_saver
    global code
    global code_hide
    global code_hide_mark
    global settingsMode
    global readyToConfig

    while True:
        for r in ROWS:
            GPIO.output(r, GPIO.LOW)
            result = [GPIO.input(COLS[0]),GPIO.input(COLS[1]),GPIO.input(COLS[2]),GPIO.input(COLS[3])]
            if min(result) == 0:
                key = MATRIX[int(ROWS.index(r))][int(result.index(0))]
                GPIO.output(r, GPIO.HIGH) #manages key keept pressed
                if key != None:
                    screen_saver = 0
                    if key == '#':
                        # region code settings verification  --------------
                        if len(code) == 0 and settingsMode == True and readyToConfig == False:
                            if show_code:
                                showMsg("headerControl","Cfg.Pwd:" + code)
                            else:
                                showMsg("headerControl","Cfg.Pwd:"+ code_hide)
                            break
                        elif len(code) == 0 and settingsMode == True and readyToConfig == True:
                            code = code + key
                            code_hide = code_hide + code_hide_mark
                            showMsg("headerControl","Code: " + code)
                            break

                        elif code[0:1] == '#' and settingsMode == True and readyToConfig == False:
                            if code[1:] == pwdRST :
                                readyToConfig = True
                                showMsg("headerControl","Pwd: Ok")
                                sleep(3)
                                showMsg("headerControl","Setting code:")
                                sleep(3)
                                if debugging:
                                    print('pwd ok')
                                code = code_hide = ''
                                break
                            else:
                                showMsg("headerControl","Pwd: Error")
                                sleep(3)
                                showMsg("headerControl","Pwd: ")
                                if debugging:
                                    print('pwd error')
                                code = code_hide = ''
                                break
                        elif code[0:1] != '#' and settingsMode == True and readyToConfig == True:
                            if changeSetting(code):
                                showMsg("Applying","code")
                                sleep(4)
                                showMsg("headerControl","Code: ")
                                code = code_hide = ''
                            else:
                                showMsg("Not Applied", "code")
                                sleep(4)
                                showMsg("headerControl","Code: ")
                                code = code_hide = ''

                            break
                        elif code[0:1] == '#' and code[1:] == _settingsCode and settingsMode == True and readyToConfig == True:
                            showMsg("headerControl","exit settings")
                            sleep(3)
                            showMsg("headerControl","Codigo: ")
                            code = code_hide = ''
                            readyToConfig = False
                            settingsMode = False
                            break
                        elif len(code) > 0 and settingsMode == True and readyToConfig == False:
                            if code == pwdRST:
                                readyToConfig = True
                                showMsg("headerControl","Pwd: OK")
                                sleep(3)
                                showMsg("headerControl","Code:")
                                if debugging:
                                    print('pwd ok')
                                code = code_hide = ''
                                break
                            else:
                                showMsg("headerControl","Pwd: Error")
                                sleep(3)
                                showMsg("headerControl","Pwd:")
                                if debugging:
                                    # disable because not working ok
                                    # DisplayMsg('pwd error',4)
                                    print('pwd error')
                                code = code_hide = ''
                                break
                        elif len(code) == 0 and settingsMode == False:
                            code = code + key
                            code_hide = code_hide + code_hide_mark
                            if show_code:
                                showMsg("headerControl","Cfg.Code:" + code)
                            else:
                                showMsg("headerControl","Cfg.Code:" + code_hide)
                            break
                        elif code[0:1] == '#' and settingsMode == False:
                            if code[1:] == _settingsCode:
                                settingsMode = True
                                showMsg("headerControl","Cfg.Pwd:")
                                code = code_hide = ''
                            break
                        
                        # endregion -------------------------------------
                        
                        # incomplete code ---------------------
                        elif len(code) < 6 and code[0:1] != '#':
                            showMsg("Codigo","Incompleto")
                            sleep(4)
                            showMsg("headerControl","Codigo: {}".format(code))

                            if debugging:
                                print('incomplete code')
                            break
                        # Just verify code ---------------------
                        elif len(code) > 5 and code[0:1] != '#':
                            activeCode(code)
                            code = code_hide = ''
                            break

                    elif key == '*':
                        if len(code) > 0:
                            code = code[0:-1]
                            code_hide = code_hide[0:-1]
                        
                    else:
                        code = code + key
                        code_hide = code_hide + code_hide_mark

                    if debugging:
                        print("Codigo: " + code)
                
                    if show_code:
                        if settingsMode == True and readyToConfig == True:
                            showMsg("headerControl","Cfg.option:" + code)
                        elif (settingsMode == True) or code[0:1] == '#':
                            showMsg("headerControl","Cfg.Pwd:" + code)
                        else:    
                            showMsg("headerControl","Codigo: " + code)
                    else:
                        if settingsMode == True and readyToConfig == True:
                            showMsg("headerControl","Cfg.option:" + code_hide)
                        elif (settingsMode == True)  or code[0:1] == '#':
                            showMsg("headerControl","Cfg.Pwd:" + code_hide)
                        else:
                            showMsg("headerControl","Codigo: " + code_hide)
                        

                        
                    
                    sleep(0.3)
            GPIO.output(r, GPIO.HIGH)
    
try:
    initial()
    disp.clear()
    showMsg(namePlace)

     # Monitor for screen saver
    thM = threading.Thread(target=monitor)
    thM.start()

    # catch keypas pressed
    thK = threading.Thread(target=PollKeypad)
    thK.start()

    cap = cv2.VideoCapture(0)
    while cap.isOpened():

        # Leer un frame de la cámara
        ret, frame = cap.read()
        if not ret:
            break

        # Decodificar QR en el frame
        frame = decode_qr(frame)

        # Salir con la tecla 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    print('\nAdios.!')
    GPIO.cleanup()
    disp.clear()

except OSError:  # Open failed
    print('Error--> ', OSError)
    logger.error(OSError)
except SystemExit as e:
    logger.error(e)
    os._exit()
finally:
    # Liberar la cámara y cerrar todas las ventanas
    cap.release()
    cv2.destroyAllWindows()
    sys.exit()


