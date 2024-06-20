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

import Adafruit_GPIO.SPI as SPI # type: ignore
import Adafruit_SSD1306 # type: ignore

import RPi.GPIO as GPIO # type: ignore

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

#----- logger section -----
logging.basicConfig(filename='history.log', level=logging.ERROR, 
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger(__name__)


#region ---- variables section  -------------

conf = open(str(pathlib.Path().resolve()) + '/config.json')
config = json.loads(conf.read())
conf.close()

code = ''
code_hide = ''
settingsMode = False
settingsCode = ''
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
settingsCode = ''

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

#endregion

#region display ----------------------------

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

def initial():
    showVersion('ver. ' + version_app)

def clear():
    draw.rectangle((0,0,width,height), outline=0, fill=0)
    disp.image(image)
    disp.display()

def showVersion(msg):
    clear()

    draw.text((0, 0),msg, font=font, fill=255)
    disp.image(image)
    disp.display()
    sleep(0.9)

    draw.text((0, 0),msg + '.', font=font, fill=255)
    disp.image(image)
    disp.display()
    sleep(0.9)

    draw.text((0, 0),msg + '..', font=font, fill=255)
    disp.image(image)
    disp.display()
    sleep(0.9)

    draw.text((0, 0),msg + '...', font=font, fill=255)
    disp.image(image)
    disp.display()
    sleep(0.9)

    draw.text((0, 0),msg + '....', font=font, fill=255)
    disp.image(image)
    disp.display()
    sleep(3)

def showMsg(msg1,msg2=None):
    draw.rectangle((0,0,width,height), outline=0, fill=0)
    disp.image(image)
    disp.display()
    
    if(msg2):
        draw.text((0, 2),f"{msg1:^40}", font=font, fill=255)
        disp.image(image)
        disp.display()

        draw.text((0, 13),f"{msg2:^40}", font=font, fill=255)
        disp.image(image)
        disp.display()
    else:
        draw.text((0, 2),f"{msg1:^40}", font=font, fill=255)
        disp.image(image)
        disp.display()

def restart():
    clear()
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
        draw.text((1, 18), "Booting.. ", font=font, fill=255)
        disp.image(image)
        disp.display()
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
        applied = True

    elif value == '2': # set matrix for hard plastic keypad
        MATRIX = config['keypad_matrix']['hardPlastic']
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
    last_capture = datetime.now()
    curl = url + api_valid_code + code + '/' + usr
    try:
        res = requests.get(curl)
        if res.status_code == 200:
            clear()
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
    global settingsCode

    settingsCode = ''
    readyToConfig = False
    settingsMode = False
    clear()


def printHeader():
    draw.rectangle((0,0,width,height), outline=0, fill=0)
    draw.text((1,0), "* <-", font=font, fill=255)
    draw.text((75,0), '# enter', font=font, fill=255)
    disp.image(image)
    disp.display()

def printHeaderSettings():
    draw.rectangle((0,0,width,height), outline=0, fill=0)
    draw.text((1,0), "* <-", font=font, fill=255)
    draw.text((75,0), '# enter', font=font, fill=255)
    draw.text((1,9), 'config', font=font, fill=255)

def monitor():
    global screen_saver
    while True:
        sleep(1)
        if screen_saver <= 60:
            screen_saver += 1
        
        if screen_saver == 60:
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
    global settingsCode
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
                            printHeaderSettings()
                            code = code + key
                            code_hide = code_hide + code_hide_mark
                            draw.text((1, 18), "Pwd:  " + code_hide, font=font, fill=255)
                            disp.image(image)
                            disp.display()
                            break
                        elif len(code) == 0 and settingsMode == True and readyToConfig == True:
                            printHeaderSettings()
                            code = code + key
                            code_hide = code_hide + code_hide_mark
                            draw.text((1, 18), "Code:  " + code, font=font, fill=255)
                            disp.image(image)
                            disp.display()
                            break
                        elif len(code) == 0 and settingsMode == False:
                            code = code + key
                            code_hide = code_hide + code_hide_mark
                            draw.text((1, 18), "Code:  " + code, font=font, fill=255)
                            disp.image(image)
                            disp.display()
                            break
                        elif code[0:1] == '#' and settingsMode == False:
                            if code[1:] == _settingsCode:
                                settingsMode = True
                                song('ok')
                                printHeaderSettings()
                                cmdLineTitle = "Pwd:                  "
                                draw.text((1, 18), cmdLineTitle, font=font, fill=255)
                                disp.image(image)
                                disp.display()
                                settingsCode = ''
                                code = code_hide = ''
                                break
                        elif code[0:1] == '#' and settingsMode == True and readyToConfig == False:
                            if code[1:] == pwdRST :
                                readyToConfig = True
                                printHeaderSettings()
                                draw.text((1, 18), "Pwd: OK         ", font=font, fill=255)
                                disp.image(image)
                                disp.display()
                                song('ok')
                                sleep(3)
                                printHeaderSettings()
                                draw.text((1, 18), "Code:           ", font=font, fill=255)
                                disp.image(image)
                                disp.display()
                                if debugging:
                                    # DisplayMsg('pwd ok',5)
                                    print('pwd ok')
                                code = code_hide = ''
                                settingsCode = ''
                                break
                            else:
                                printHeaderSettings()
                                draw.text((1, 18), "Pwd: Error         ", font=font, fill=255)
                                disp.image(image)
                                disp.display()
                                song('fail')
                                sleep(3)
                                printHeaderSettings()
                                draw.text((1, 18), "Pwd:         ", font=font, fill=255)
                                disp.image(image)
                                disp.display()
                                if debugging:
                                    # disable because not working ok
                                    # DisplayMsg('pwd error', 5)
                                    print('pwd error')
                                code = code_hide = ''
                                break
                        elif code[0:1] != '#' and settingsMode == True and readyToConfig == True:
                            if changeSetting(code):
                                draw.text((1, 10), "Applying", font=font, fill=255)
                                draw.text((3, 18), "code", font=font, fill=255)
                                disp.image(image)
                                disp.display()
                                sleep(4)
                                song('ok')
                                printHeaderSettings()
                                draw.text((3, 18), "Code: ", font=font, fill=255)
                                disp.image(image)
                                disp.display()
                                code = code_hide = ''
                            else:
                                draw.rectangle((0,0,width,height), outline=0, fill=0)
                                draw.text((1, 10), "Not Applied", font=font, fill=255)
                                draw.text((3, 18), "code ", font=font, fill=255)
                                disp.image(image)
                                disp.display()
                                sleep(4)
                                song('fail')
                                printHeaderSettings()
                                draw.text((3, 18), "Code: ", font=font, fill=255)
                                disp.image(image)
                                disp.display()
                                code = code_hide = ''

                            break
                        elif code[0:1] == '#' and code[1:] == _settingsCode and settingsMode == True and readyToConfig == True:
                            printHeaderSettings()
                            draw.text((3, 18), "exit settings", font=font, fill=255)
                            disp.image(image)
                            disp.display()
                            song('ok')
                            sleep(3)
                            printHeader()
                            draw.text((3, 18), "Codigo:           ", font=font, fill=255)
                            disp.image(image)
                            disp.display()
                            code = code_hide = ''
                            settingsCode = ''
                            readyToConfig = False
                            settingsMode = False
                            break
                        elif len(code) > 0 and settingsMode == True and readyToConfig == False:
                            if code == pwdRST:
                                readyToConfig = True
                                printHeaderSettings()
                                draw.text((3, 18), "Pwd: OK         ", font=font, fill=255)
                                disp.image(image)
                                disp.display()
                                song('ok')
                                sleep(3)
                                printHeaderSettings()
                                draw.text((3, 18), "Code:           ", font=font, fill=255)
                                disp.image(image)
                                disp.display()
                                if debugging:
                                    # disable because not working ok
                                    # DisplayMsg('pwd ok', 5)
                                    print('pwd ok')
                                code = code_hide = ''
                                settingsCode = ''
                                break
                            else:
                                printHeaderSettings()
                                draw.text((3, 18), "Pwd: Error         ", font=font, fill=255)
                                disp.image(image)
                                disp.display()
                                song('fail')
                                sleep(3)
                                printHeaderSettings()
                                draw.text((3, 18), "Pwd:         ", font=font, fill=255)
                                disp.image(image)
                                disp.display()
                                if debugging:
                                    # disable because not working ok
                                    # DisplayMsg('pwd error',4)
                                    print('pwd error')
                                code = code_hide = ''
                                break
                        # endregion -------------------------------------
                        
                        # incomplete code ---------------------
                        elif len(code) < 6 and code[0:1] != '#':
                            printHeader()
                            draw.text((3, 18), "Codigo incompleto    ", font=font, fill=255)
                            disp.image(image)
                            disp.display()
                            song('fail')
                            sleep(3)
                            printHeader()
                            draw.text((3, 18), "Codigo: {}             ".format(code), font=font, fill=255)
                            disp.image(image)
                            disp.display()
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
                
                    draw.rectangle((0,0,width,height), outline=0, fill=0)
                    draw.text((1,0), "* <-", font=font, fill=255)
                    draw.text((75,0), '# enter', font=font, fill=255)
                    if show_code:
                        draw.text((1, 18), "Codigo:  " + code, font=font, fill=255)
                    else:
                        draw.text((1, 18), "Codigo:  " + code_hide, font=font, fill=255)
                    
                    disp.image(image)
                    disp.display()

                    if debugging:
                        print("Codigo: " + code)
                    
                    sleep(0.3)
            GPIO.output(r, GPIO.HIGH)
    
try:
    initial()
    clear()
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
    clear()
    

except OSError:  # Open failed
    print('Error--> ', OSError)
    logger.error(OSError)
except SystemExit as e:
    import os
    logger.error(e)
    os._exit()
finally:
    # Liberar la cámara y cerrar todas las ventanas
    cap.release()
    cv2.destroyAllWindows()
    sys.exit()

