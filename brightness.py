#!/usr/bin/python3

import paho.mqtt.client as mqtt
import time
import threading
from secrets import HOSTNAME, CLIENT, UNAME, PWORD

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

bs = BrightnessSetter()

def on_connect(client, userdata, flags, rc):
    print('Connected with result code ' + str(rc))
    client.subscribe('touchpanel/brightness')

def on_message(client, userdata, msg):
    print(msg.topic + ' ' + str(msg.payload))
    if msg.topic == 'touchpanel/brightness':
        print('Payload: ', msg.payload)
        try:
            brightness = int(float(msg.payload.decode('utf-8'))) 
            bs.set_brightness_smooth(brightness)
        except Exception as e:
            print(e)


def on_log(client, userdata, level, buf):
    print('log: ', buf)




client = mqtt.Client(client_id=CLIENT, clean_session=True, protocol=mqtt.MQTTv31)
print('Running...')
client.loop_start()
retry_count = 0
while(True):
    try:
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_log = on_log
        client.username_pw_set(username=UNAME, password=PWORD)
        status = client.connect(HOSTNAME)
        retry_count = 0
        while status == 0:
            status = client.loop_forever()
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

client.loop_stop()

