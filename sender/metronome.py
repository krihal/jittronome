#! /usr/bin/env python3

#
# (C) SUNET (www.sunet.se)
#


import sys
import time
import wave
import redis
import pyaudio
import argparse

from datetime import datetime


class Metronome():
    def __init__(self, bpm, redis_host, redis_port, name):
        self.bpm = int(bpm)
        self.redis_client = redis.Redis(
            host=redis_host, port=redis_port, db=0)
        self.name = name
        self.p = pyaudio.PyAudio()
        high = wave.open('high.wav', "rb")
        low = wave.open('low.wav', "rb")

        self.stream = self.p.open(format=self.p.get_format_from_width(high.getsampwidth()),
                                  channels=high.getnchannels(),
                                  rate=high.getframerate(),
                                  output=True)

        self.high_data = high.readframes(2048)
        self.low_data = low.readframes(2048)

    def metronome(self):
        ticks = 0
        while True:
            for i in range(4):
                ticks += 1
                now = datetime.now().timestamp()
                if i % 4 == 0:
                    self.stream.write(self.low_data)
                else:
                    self.stream.write(self.high_data)

                self.redis_client.lpush(self.name, f'{now} {i}')
                print(f'Pushed to Redis: {now} {i}')
                time.sleep(60 / self.bpm)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", '--bpm', default=120)
    parser.add_argument('-r', '--redis_host')
    parser.add_argument('-p', '--redis_port', default=6379)
    parser.add_argument('-n', '--sender_name')
    args = parser.parse_args()

    if args.redis_host is None or args.sender_name is None:
        print('Use -h or --help to see required arguments.')
        sys.exit(0)

    m = Metronome(args.bpm, args.redis_host, args.redis_port, args.sender_name)
    m.metronome()
