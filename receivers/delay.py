#! /usr/bin/env python3

#
# (C) SUNET (www.sunet.se)
#


import sys
import math
import time
import redis
import queue
import struct
import pyaudio
import argparse
import threading

from datetime import datetime
from influxdb import InfluxDBClient
from rfc3339 import rfc3339


class DelayListener(object):
    def __init__(self, influx_host, influx_port, redis_host, redis_port,
                 listener_name):
        self.listener_queue = queue.Queue()
        self.listener_name = listener_name

        self.client = InfluxDBClient(host=influx_host, port=influx_port)
        self.client.switch_database('metronome')

        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)

        self.format = pyaudio.paInt16
        self.short_normalize = (1.0/32768.0)
        self.input_block_time = 0.005
        self.input_frames_per_block = int(5000 * self.input_block_time)

    def get_rms(self, block):
        count = len(block)/2
        format = "%dh" % (count)
        shorts = struct.unpack(format, block)
        sum_squares = 0.0

        for sample in shorts:
            n = sample * self.short_normalize
            sum_squares += n*n

        return math.sqrt(sum_squares / count)

    def producer(self):
        timestamp = 0
        errorcount = 0

        pulse = 0
        pulse_start = 0
        trigger_high = False

        pa = pyaudio.PyAudio()
        stream = pa.open(format=self.format,
                         channels=1,
                         rate=5000,
                         input=True,
                         frames_per_buffer=self.input_frames_per_block)

        while True:
            try:
                block = stream.read(self.input_frames_per_block)
            except IOError as e:
                errorcount += 1
                print("(%d) Error recording: %s" % (errorcount, e))
                continue

            amplitude = self.get_rms(block)

            if amplitude > 0.0001:
                if pulse_start == 0:
                    timestamp = datetime.now().timestamp()
                    trigger_high = False

                if amplitude > 0.1:
                    trigger_high = True

                pulse_start += 1
                if pulse_start == 6:
                    if not trigger_high:
                        pulse = 0
                    else:
                        pulse += 1

                    self.listener_queue.put([timestamp, pulse])
            else:
                pulse_start = 0

    def consumer(self):
        self.redis_client.delete(self.listener_name)
        influx_results = []

        while True:
            timestamp, pulse = self.listener_queue.get()
            tmp_str = str(self.redis_client.rpop(self.listener_name))
            try:
                sent_timestamp, sender_pulse = tmp_str.split(' ')
            except Exception:
                continue
            sender_pulse = int(sender_pulse.replace("'", ""))

            time_sent = float(sent_timestamp[2:])
            time_recv = float(timestamp)

            if sender_pulse != pulse:
                tmp_str = str(self.redis_client.rpop(self.listener_name))
                influx_results = []
                print('Pulse missmatch, dropping results and restarting')
                continue
            else:
                delay = time_recv - time_sent

                if delay < 0:
                    delay = 0.0

            current_timestamp = datetime.fromtimestamp(timestamp)

            json_data = [{
                "measurement": "delay",
                "tags": {
                    'name': self.listener_name,
                },
                'fields': {
                    'delay': delay
                },
                "time": rfc3339(current_timestamp)
            }]

            influx_results.append(json_data)

            if pulse == 0:
                for result in influx_results:
                    res = self.client.write_points(result)
                influx_results = []

                if res:
                    print(f'Wrote result to InfluxDB, last delay: {delay}')
                else:
                    print(
                        f'Failed to write result to InfluxDB, delay was: {delay}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--redis_host')
    parser.add_argument('-p', '--redis_port', default=6379)
    parser.add_argument('-i', '--influx_host')
    parser.add_argument('-o', '--influx_port', default=8086)
    parser.add_argument('-n', '--listener_name')
    args = parser.parse_args()

    if None in [args.influx_host, args.redis_host, args.listener_name]:
        print('Use -h or --help to see required arguments.')
        sys.exit(0)

    listener = DelayListener(args.influx_host, args.influx_port,
                             args.redis_host, args.redis_port,
                             args.listener_name)
    threading.Thread(target=listener.consumer, daemon=True).start()
    threading.Thread(target=listener.producer, daemon=False).start()
