import math
import time
import redis
import queue
import struct
import pyaudio
import threading

from datetime import datetime
from influxdb import InfluxDBClient

q = queue.Queue()
client = InfluxDBClient(host='192.168.122.199', port=8086)
client.switch_database('metronome')
#client.create_retention_policy('default_policy', '3d', 3, default=True)

FORMAT = pyaudio.paInt16
SHORT_NORMALIZE = (1.0/32768.0)
CHANNELS = 1
RATE = 5000
INPUT_BLOCK_TIME = 0.008
INPUT_FRAMES_PER_BLOCK = int(RATE * INPUT_BLOCK_TIME)

ticks = 0


def get_rms(block):
    count = len(block)/2
    format = "%dh" % (count)
    shorts = struct.unpack(format, block)
    sum_squares = 0.0
    for sample in shorts:
        n = sample * SHORT_NORMALIZE
        sum_squares += n*n

    return math.sqrt(sum_squares / count)


def producer():
    global ticks
    pa = pyaudio.PyAudio()
    stream = pa.open(format=FORMAT,
                     channels=CHANNELS,
                     rate=RATE,
                     input=True,
                     frames_per_buffer=INPUT_FRAMES_PER_BLOCK)

    timestamp = 0
    last_timestamp = 0
    errorcount = 0

    trigger_high = False
    pulse_start = 0
    pulse = 0

    while True:
        try:
            block = stream.read(INPUT_FRAMES_PER_BLOCK)
        except IOError as e:
            errorcount += 1
            print("(%d) Error recording: %s" % (errorcount, e))

        amplitude = get_rms(block)
        if amplitude > 0.0001:
            if pulse_start == 0:
                dt = datetime.now()
                timestamp = dt.timestamp()
                trigger_high = False

            if amplitude > 0.1:
                trigger_high = True
            pulse_start += 1
            if pulse_start == 6:
                if trigger_high == False:
                    pulse = 0
                else:
                    pulse += 1

                last_timestamp = timestamp
                q.put([ticks, timestamp, trigger_high, pulse])
        else:
            pulse_start = 0


def consumer():
    global ticks
    print('Consumer started')

    redis_client = redis.Redis(host='192.168.122.199', port=6379, db=0)

    redis_client.delete('packets_sent_x')
    bar = []
    
    while True:
        ticks,timestamp,trigger_high,pulse = q.get()
        tmp_str = str(redis_client.rpop('packets_sent_x'))
        try:            
            sent_timestamp,packets_sent,highlow,sender_pulse = tmp_str.split(' ')
        except Exception:
            continue
        sent = int(packets_sent.replace("'", ""))
        sender_pulse = int(sender_pulse.replace("'", ""))        
        recv = ticks
        
        time_sent = float(sent_timestamp[2:])
        time_recv = float(timestamp)

        # print(f'{time_sent} {time_recv}')

        if "low" in highlow:
            trigger_sender = False
        else:
            trigger_sender = True
        

        if sender_pulse != pulse:
            tmp_str = str(redis_client.rpop('packets_sent_x'))
            bar = []
            print(f'pulse missmatch in bar dropping bar')
            continue
        else:
            delay = time_recv - time_sent

        from rfc3339 import rfc3339
        print(timestamp)
        d = datetime.fromtimestamp(timestamp)
        
        json_data = [
            {
                "measurement": "zoom_delayx",
                "tags": {
                    'name': "Receiver 1",
                },
                'fields': {
                    'delay': delay
                },
                "time": rfc3339(d)
            }
        ]
        bar.append(json_data)
        if pulse == 0:
            for mp in bar:
                client.write_points(mp)
            bar = []
            print(f' write to Influx')


        # print(f'Ticks: {recv}, Delay: {delay}')
        

if __name__ == '__main__':
    threading.Thread(target=consumer, daemon=True).start()
    threading.Thread(target=producer, daemon=False).start()
