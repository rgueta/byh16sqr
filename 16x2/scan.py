#scan app. version for 16x2 displays     ------------------------------------

import cv2 # type: ignore
from pyzbar import pyzbar # type: ignore
from time import sleep
import requests
import json
import pathlib
import logging
from datetime import datetime
import os
import sys
from threading import Thread

import RPi.GPIO as GPIO # type: ignore
from Adafruit_CharLCD import Adafruit_CharLCD 

#----- logger section -----
logging.basicConfig(filename='history.log', level=logging.ERROR, 
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger=logging.getLogger(__name__)

#region ---- variables section  -------------
conf = open(str(pathlib.Path().resolve()) + '/config.json')
config = json.loads(conf.read())
conf.close()

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
#lcd variables   -------------------
cols = config['screen']['cols']
lines = config['screen']['lines']
rs = config['screen']['rs']
en = config['screen']['en']
d4 = config['screen']['d4']
d5 = config['screen']['d5']
d6 = config['screen']['d6']
d7 = config['screen']['d7']
backlight = config['screen']['backlight']

#decode and code verification
acc = 0
acc_code = 0
first_code = ''
last_capture = datetime.now()

#endregion

#region display ----------------------------

#  Initialize LCD (must specify pinout and dimensions)
# GPIO.setmode(GPIO.BOARD)
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(buzzer_pin,GPIO.OUT)
# GPIO.output(buzzer_pin, True)

buzzer = GPIO.PWM(buzzer_pin, 10)
buzzer.start(0)

GPIO.setup(15, GPIO.OUT) # Backlight enable

lcd = Adafruit_CharLCD(rs=rs, en=en, d4=d4, d5=d5, d6=d6, d7=d7,
                       cols=cols, lines=lines, backlight=backlight)
#endregion display -------------------

def initial():
    showVersion('ver. ' + version_app)

def showVersion(msg):
    lcd.clear()
    showMsg(msg + '.')
    sleep(0.9)

    lcd.clear()
    showMsg(msg + '..')
    sleep(0.9)

    lcd.clear()
    showMsg(msg + '...')
    sleep(0.9)

    lcd.clear()
    showMsg(msg + '....')
    sleep(3)

def showMsg(msg1,msg2=None):
    lcd.clear()
    # init_blank = len(msg) // 2
    
    if(msg2):
        lcd.message(f"{msg1:^16}" + "\n")
        lcd.message(f"{msg2:^16}")
    else:
        lcd.message(f"{msg1:^16}")

def restart():
    lcd.clear()
    showMsg('Restarting..')
    cap.release()
    cv2.destroyAllWindows()
    os.execl(sys.executable, sys.executable, *sys.argv)

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
            if diff_time > 13:
                GPIO.output(buzzer_pin,GPIO.HIGH)
                sleep(0.5)
                GPIO.output(buzzer_pin,GPIO.LOW)
                
                if qr_data == password:
                    restart();
                    return
            
                screen_saver = 0
                print("{}.- Data: '{}' | Type: '{}' | Acc-code: '{}' | Diff: '{}' "
                    .format(str(acc),qr_data, qr_type, acc_code, str(diff_time)))
                
                activeCode(qr_data)

def activeCode(code):
    global last_capture
    last_capture = datetime.now()
    curl = url + api_valid_code + code + '/' + usr
    try:
        res = requests.get(curl)
        if res.status_code == 200:
            print(res.json())
            lcd.clear()
            showMsg('Bienvenido')
            sleep(5)
            showMsg(namePlace)
            return True
        else:
            lcd.clear()
            showMsg('Codigo','No valido')
            sleep(7)
            showMsg(namePlace)
            return False
    except requests.exceptions.RequestException as e:
        logger.error(e)
        return False

def tone(pin, frequency, duration):
    pin.start(100)
    pin.ChangeDutyCycle(duration)  # volume
    pin.ChangeFrequency(frequency)
    sleep(2)
    pin.stop()
    # GPIO.cleanup()

def song(name):
    if name == 'initial':
        tone(buzzer, 1440, 30)
        tone(buzzer, 1150, 30)
        tone(buzzer, 1440, 30)
    elif name == 'fail':
        tone(buzzer, 100, 50)
    elif name == 'ok':
        tone(buzzer, 1100, 20)
        tone(buzzer, 1500, 20)

def screenSaver():
    lcd.clear()
    showMsg('Screen saver')
    sleep(4)
    lcd.set_backlight(0)


def monitor():
    global screen_saver
    while True:
        sleep(1)
        if screen_saver <= 60:
            screen_saver += 1
        else:
            screenSaver()



try:
    initial()
    print('scan app ready..')
    lcd.clear()
    showMsg(namePlace)
    Thread(target=monitor).start()

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
    lcd.clear()

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


