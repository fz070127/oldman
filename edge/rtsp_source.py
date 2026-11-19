"""Paced files and a one-frame live capture buffer, with a fresh timeline per connection."""
import logging
import math
import threading
import time
from contextlib import contextmanager

import cv2


class Source:
    def __init__(self, config, stride, stop):
        keys = [k for k in ("video_file", "rtsp_url", "camera_index") if config.get(k) is not None]
        if len(keys) != 1:
            raise ValueError("Select one video_file, rtsp_url or camera_index")
        self.key = keys[0]
        self.value = config[self.key]
        self.is_file = self.key == "video_file"
        self.fallback = config.get("fps_fallback", 30)
        self.stride = stride
        self.stop = stop

    @contextmanager
    def open(self):
        if self.key == "rtsp_url":
            cap = cv2.VideoCapture(self.value, cv2.CAP_FFMPEG, [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000])
        else:
            cap = cv2.VideoCapture(self.value)
        try:
            if not cap.isOpened():
                raise OSError(f"Cannot open {self.key}")
            self.fps = cap.get(cv2.CAP_PROP_FPS)
            if not math.isfinite(self.fps) or self.fps <= 0:
                self.fps = self.fallback
            self.origin = time.perf_counter()
            self.wall = time.time()
            logging.info("source fps=%.4f stride=%d origin_mono=%.9f", self.fps, self.stride, self.origin)
            if self.is_file:
                yield self._read(cap)
            else:
                with self._live(cap) as frames:
                    yield frames
        finally:
            cap.release()

    def _read(self, cap):
        index = 0
        while not self.stop.is_set() and cap.grab():
            index += 1
            if (index - 1) % self.stride:
                continue
            ok, image = cap.retrieve()
            if not ok:
                raise OSError(f"Decode error at frame {index}")
            if self.is_file:
                due = self.origin + (index - 1) / self.fps
                if self.stop.wait(max(0, due - time.perf_counter())):
                    return
                captured = self.wall + (index - 1) / self.fps
            else:
                captured = time.time()
            yield index, captured, image
        if self.is_file and not self.stop.is_set():
            expected = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            if index == 0 or (expected > 0 and index < round(expected)):
                raise OSError(f"Incomplete video: decoded {index} of {expected} frames")

    @contextmanager
    def _live(self, cap):
        cv = threading.Condition()
        latest = None
        ended = threading.Event()
        cancel = threading.Event()

        def capture():
            nonlocal latest
            try:
                for item in self._read(cap):
                    with cv:
                        latest = item
                        cv.notify()
                    if cancel.is_set():
                        break
            except (cv2.error, OSError):
                logging.exception("Live capture failed")
            finally:
                with cv:
                    ended.set()
                    cv.notify()

        def consume():
            previous = 0
            while not self.stop.is_set():
                with cv:
                    cv.wait_for(lambda: ended.is_set() or (latest and latest[0] > previous), timeout=1)
                    if latest and latest[0] > previous:
                        item = latest
                    elif ended.is_set():
                        return
                    else:
                        continue
                previous = item[0]
                yield item

        thread = threading.Thread(target=capture, name="capture")
        thread.start()
        try:
            yield consume()
        finally:
            cancel.set()
            thread.join()
