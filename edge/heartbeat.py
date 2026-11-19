import logging
import threading
import time
from datetime import datetime

import psutil


class Heartbeat:
    def __init__(self, publisher, interval=30):
        self.publisher = publisher
        self.interval = interval
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.frames = 0
        self.thread = threading.Thread(target=self._run, name="heartbeat")
        self.thread.start()

    def tick(self):
        with self.lock:
            self.frames += 1

    def _run(self):
        start = time.monotonic()
        psutil.cpu_percent()
        while not self.stop.wait(self.interval):
            now = time.monotonic()
            with self.lock:
                fps = self.frames / (now - start)
                self.frames = 0
            start = now
            payload = dict(deviceNo=self.publisher.device, fps=round(fps, 2),
                           cpu=psutil.cpu_percent(), mem=psutil.virtual_memory().percent,
                           ts=datetime.now().astimezone().isoformat())
            self.publisher.heartbeat(payload)
            logging.info("heartbeat %s", payload)

    def close(self):
        self.stop.set()
        self.thread.join()
