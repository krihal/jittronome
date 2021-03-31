#
# IF YOU'RE TRYING TO RE-USE THIS FOR ANYTHING YOU'RE INSANE!
#

import pyaudio
import struct
import math

import sys
import time
import queue
from influxdb import InfluxDBClient
import threading
import psycopg2

FORMAT = pyaudio.paInt16
SHORT_NORMALIZE = (1.0/32768.0)
CHANNELS = 1
RATE = 5000
INPUT_BLOCK_TIME = 0.008
INPUT_FRAMES_PER_BLOCK = int(RATE * INPUT_BLOCK_TIME)
PULSE_AMPLITUDE = 0.0005

samples_queue = queue.Queue()

client = None
db_cursor = None
receiver_name = ''


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
    ticked = False
    ticks = 0
    high = 0
    timestamp = 0
    last_timestamp = 0
    delta = 0

    pa = pyaudio.PyAudio()
    stream = pa.open(format=FORMAT,
                     channels=CHANNELS,
                     rate=RATE,
                     input=True,
                     frames_per_buffer=INPUT_FRAMES_PER_BLOCK)

    while True:
        try:
            block = stream.read(INPUT_FRAMES_PER_BLOCK)
        except IOError as e:
            print(f'Recording failed, skipping sample: {e}')
            continue

        if get_rms(block) > PULSE_AMPLITUDE:
            high += 1
            timestamp = time.time() * 1000
            if ticks == 0:
                delta = 0.0
            else:
                delta = timestamp - last_timestamp - 500

            if ticked is False and high > 2:
                ticks += 1
                last_timestamp = timestamp
                samples_queue.put(
                    [ticks, timestamp, delta])
                ticked = True
        else:
            ticked = False
            high = 0


def consumer():
    while True:
        ticks, timestamp, delta = samples_queue.get()
        sql_data = f'INSERT INTO measurements (tick, description, timestamp_rx)' + \
            f' VALUES ({ticks}, {receiver_name}, {timestamp});'
        json_data = [
            {
                "measurement": "zoom_jitter",
                "tags": {
                    'name': receiver_name,
                },
                'fields': {
                    "ticks": ticks,
                    "jitter": delta,
                }
            }
        ]

        try:
            client.write_points(json_data)
        except Exception:
            print('InfluxDB write error')
            continue

        try:
            db_cursor.execute(sql_data)
        except Exception:
            print('PostgreSQL write error')
            continue


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(
            f'Usage: {sys.argv[0]} <listener name> <InfluxDB + Postgres host>')
        sys.exit(0)

    receiver_name = sys.argv[1]

    try:
        client = InfluxDBClient(host=sys.argv[2], port=8086)
        client.switch_database('metronome')
    except Exception:
        print('Failed to connecto InfluxDB, qutting')
        sys.exit(0)

    try:
        db_conn = psycopg2.connect(
            host=sys.argv[2], dbname='measurements', user='measure',
            password='foobar123')
        db_cursor = db_conn.cursor()
    except Exception:
        print('Failed to connect Postgres, quitting')
        sys.exit(0)

    print('Starting threads...')
    threading.Thread(target=consumer, daemon=True).start()
    threading.Thread(target=producer, daemon=False).start()
