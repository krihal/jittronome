#! /usr/bin/env python3


import sys
import math
import time
import queue
import struct
import pyaudio
import argparse
import threading

from influxdb import InfluxDBClient


class JitterListener(object):
    def __init__(self, redis_host, redis_port, listener_name):
        self.listener_queue = queue.Queue()
        self.listener_name = listener_name
        self.client = InfluxDBClient(host=redis_host, port=redis_port)
        self.client.switch_database('metronome')
        self.format = pyaudio.paInt16
        self.short_normalize = (1.0/32768.0)
        self.input_block_time = 0.005
        self.input_frames_per_block = int(5000 * self.input_block_time)
        self.ticks = 0

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
        ticked = False
        high = 0
        timestamp = 0
        last_timestamp = 0
        timestamp_delta = 0
        errorcount = 0

        pa = pyaudio.PyAudio()
        stream = pa.open(format=self.format,
                         channels=1,
                         rate=5000,
                         input=True,
                         frames_per_buffer=self.input_frames_per_block)

        while True:
            try:
                block = stream.read(self.input_frames_per_block)
                timestamp = time.time() * 1000
            except IOError as e:
                errorcount += 1
                print("(%d) Error recording: %s" % (errorcount, e))

            amplitude = self.get_rms(block)
            if amplitude > 0.0005:
                high += 1
                if self.ticks == 0:
                    timestamp_delta = 0.0
                else:
                    timestamp_delta = timestamp - last_timestamp - 500

                if ticked is False and high > 2:
                    self.ticks += 1
                    last_timestamp = timestamp
                    self.listener_queue.put(
                        [self.ticks, timestamp, timestamp_delta])
                    ticked = True
            else:
                ticked = False
                high = 0

    def consumer(self):
        while True:
            ticks, timestamp, timestamp_delta = self.listener_queue.get()
            json_data = [{
                "measurement": "zoom_jitter",
                "tags": {
                    'name': self.listener_name,
                },
                'fields': {
                    "ticks": ticks,
                    "jitter": timestamp_delta,
                }
            }]

            self.client.write_points(json_data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-r', '--redis_host')
    parser.add_argument('-p', '--redis_port', default=6379)
    parser.add_argument('-n', '--listener_name')
    args = parser.parse_args()

    if args.redis_host is None or args.listener_name is None:
        print('Use -h or --help to see required arguments.')
        sys.exit(0)

    listener = JitterListener(
        args.redis_host, args.redis_port, args.listener_name)
    threading.Thread(target=listener.consumer, daemon=True).start()
    threading.Thread(target=listener.producer, daemon=False).start()
