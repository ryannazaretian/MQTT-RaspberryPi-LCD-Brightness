#!/usr/bin/python3

import paho.mqtt.client as mqtt
import traceback
import time
import threading
import sys
if sys.platform == 'win32':
    import winsound
else:
    import RPi.GPIO as GPIO
from mqtt_secrets import SERVER, UNAME, PWORD
import socket


class Buzzer(threading.Thread):
    def __init__(self, buzzer_pin):
        threading.Thread.__init__(self)
        self.queue_lock = threading.Lock()
        self.queue_event = threading.Event()
        self.beep_queue = []
        self.pin = buzzer_pin
        self.running = True
        if sys.platform != 'win32':
            GPIO.cleanup()
            GPIO.setmode(GPIO.BOARD)
            GPIO.setup(self.pin, GPIO.OUT)
        self.start()

    def enqueue(self, beep_list=[]):
        if len(beep_list):
            self.queue_lock.acquire()
            for t in beep_list:
                self.beep_queue.insert(0,t)
            self.queue_lock.release()
            self.queue_event.set()

    def flush_queue(self):
        self.queue_lock.acquire()
        self.beep_queue = []
        if sys.platform != 'win32':
            GPIO.output(self.pin, 0)
        self.queue_event.clear()

        self.queue_lock.release()

    def kill(self):
        self.running = False

    def beep_delay(self, period):
        self.enqueue([(0, period / 1000.0)])

    def beep(self, num_of_beeps, period = None, beep_on = None, beep_off = None, cancel_previous=True):

        if period:
            beep_on = period / 2000.0
            beep_off = period / 2000.0
        else:
            beep_on /= 1000.0
            beep_off /= 1000.0


        if beep_on is None or beep_off is None:
            raise AttributeError('You must provide either a period or beep_on and beep_off')

        beep_list = []

        if num_of_beeps > 1:
            for i in range(0, num_of_beeps * 2 + 1):
                beep_output = i & 1
                beep_time = beep_on if beep_output else beep_off
                beep_list += [(beep_output, beep_time)]
        elif num_of_beeps == 1:
            beep_list = [(1 if beep_on > 0 else 0, beep_on + beep_off)]
        else:
            return

        if cancel_previous:
            self.flush_queue()
        self.enqueue(beep_list)

    def run(self):
        print('Running beep thread')
        while self.running:
            try:
                beep = None
                self.queue_event.wait(0.1)
                self.queue_lock.acquire()
                if len(self.beep_queue) > 0:
                    beep = self.beep_queue.pop()
                    if len(self.beep_queue) == 0:
                        self.queue_event.clear()
                self.queue_lock.release()
                if beep:
                    print(beep)
                    (beep_output, beep_time) = beep
                    if beep_output:
                        if sys.platform == 'win32':
                            winsound.Beep(2800, int(beep_time*1000.0))
                        else:
                            GPIO.output(self.pin, 1)
                            time.sleep(beep_time)
                            GPIO.output(self.pin, 0)
                    else:
                        time.sleep(beep_time)
            except Exception as e:
                print (traceback.format_exc())




class BrightnessSetter(threading.Thread):
    def __init__(self, min_brightness=0, max_brightness=255, transition_time = 0.5):
        threading.Thread.__init__(self)
        self.min = min_brightness
        self.max = max_brightness
        self.transition_time = transition_time
        self.current_brightness = int((self.min + self.max) / 2)
        self.target_brightness = None
        self._busy_lock = threading.Lock()
        self.set_brightness_immediate(self.current_brightness)
    
    def set_brightness_immediate(self, brightness):
        self._busy_lock.acquire()
        self._set_brightness_immediate(brightness)
        self._busy_lock.release()

    def _set_brightness_immediate(self, brightness):
        self.current_brightness = brightness
        if brightness in range(self.min,self.max+1):
            f = open('/sys/class/backlight/rpi_backlight/brightness', 'w')
            f.write(str(brightness))
            f.close()
        else:
            raise IndexError('The value ({val}) is not within the range of {min_val} - {max_val}'.format(val=brightness, min_val=self.min, max_val=self.max))

    def run(self):
        self._busy_lock.acquire()
        target_brightness = self.target_brightness
        while self.current_brightness != self.target_brightness:
            if self.current_brightness < self.target_brightness:
                steppings = range(self.current_brightness, self.target_brightness + 1)
            else:
                steppings = range(self.current_brightness, self.target_brightness - 1, -1)
            print('Changing brightness from {current} to {target}...'.format(current=self.current_brightness, target=target_brightness))
            time_per_stepping = self.transition_time / len(steppings)
            for i in steppings:
              self._set_brightness_immediate(i)
              time.sleep(time_per_stepping)
              if self.target_brightness != target_brightness:
                  target_brightness = self.target_brightness
                  break
            print('Done changing brightness!')
        threading.Thread.__init__(self)
        self._busy_lock.release()

    def set_brightness_smooth(self, brightness):
        self.target_brightness = brightness
        if not self.is_alive():
            self.start()

if sys.platform != 'win32':
    bs = BrightnessSetter()
buzzer = Buzzer(7)
buzzer.beep(2, 200)


def on_connect(client, userdata, flags, rc):
    print('Connected with result code ' + str(rc))
    if sys.platform != 'win32':
        client.subscribe('touchpanel/brightness')
    client.subscribe('touchpanel/security_info')
    client.subscribe('touchpanel/security_alert')
    client.subscribe('touchpanel/security_pending')
    client.subscribe('touchpanel/security_clear')
    client.subscribe('touchpanel/security_armed')
    client.subscribe('touchpanel/security_disarmed')
    buzzer.beep(1, 500, cancel_previous=False)

def on_disconnect():
    buzzer.beep(2, 500, cancel_previous=False)

def on_message(client, userdata, msg):
    print(msg.topic + ' ' + str(msg.payload))
    try: 
        if msg.topic == 'touchpanel/brightness':

            brightness = int(float(msg.payload.decode('utf-8'))) 
            bs.set_brightness_smooth(brightness)
        elif msg.topic == 'touchpanel/security_info':
            buzzer.beep(3, 200)
        elif msg.topic == 'touchpanel/security_alert':
            buzzer.beep(10000, 100)
        elif msg.topic == 'touchpanel/security_clear':
            buzzer.flush_queue()
        elif msg.topic == 'touchpanel/security_pending':
            buzzer.beep(50, beep_on=100, beep_off=900)
            for i in range(10):
                buzzer.beep(4, beep_on=50, beep_off=75, cancel_previous=False)
                buzzer.beep_delay(500)
        elif msg.topic == 'touchpanel/security_armed':
            buzzer.beep(1, 500)
        elif msg.topic == 'touchpanel/security_disarmed':
            buzzer.beep(2, beep_on=200, beep_off=75)

    except Exception as e:
        print(e)



def on_log(client, userdata, level, buf):
    print('log: ', buf)



if __name__ == '__main__':
    hostname = socket.gethostname()
    client = mqtt.Client(client_id=hostname, clean_session=True)
    print('Running...')
#    client.loop_start()
    retry_count = 0
    while(True):
        try:
            print('Connecting...')
            client.on_connect = on_connect
            client.on_message = on_message
            client.on_disconnect = on_disconnect
            client.on_log = on_log
            client.username_pw_set(username=UNAME, password=PWORD)
            status = client.connect(SERVER)
            retry_count = 0
            while status == 0:
                status = client.loop(timeout=1.0)
            print ('Error {d} occured, reconnecting...'.format(d=status))
            client.disconnect()
            time.sleep(5)
        except KeyboardInterrupt:
            break   
        except ConnectionRefusedError:
            print ('Could not connect {d}...'.format(d=retry_count))
            retry_count += 1
            time.sleep(5)
        except Exception as e:
            print('Error: ', e)


