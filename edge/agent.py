"""Edge fall agent. Run python agent.py --config config.yaml."""
import argparse
from collections import deque
import logging
import math
import signal
import threading
import time
from pathlib import Path

import cv2
import yaml

from detector_wrapper import Pose, StreamDetector
from heartbeat import Heartbeat
from mqtt_client import Publisher
from rtsp_source import Source


def load_settings(path):
    with path.open(encoding="utf-8") as stream:
        cfg = yaml.safe_load(stream)
    for section, key in ((cfg, "store"), (cfg, "video_file"), (cfg["detector"], "rules"),
                         (cfg["detector"], "weights")):
        if section.get(key) is not None:
            section[key] = str((path.parent / section[key]).resolve())
    return cfg


def run(cfg, stride, stop):
    if type(stride) is not int or stride < 1:
        raise ValueError("downsample must be a positive integer")
    for value in (cfg.get("heartbeat_sec", 30), cfg.get("fps_fallback", 30)):
        if not math.isfinite(value) or value <= 0:
            raise ValueError("heartbeat_sec and fps_fallback must be positive")
    source = Source(cfg, stride, stop)
    settings = cfg["detector"]
    pose = Pose(Path(settings["weights"]), settings["cpu_threads"], settings["imgsz"])
    publisher = Publisher(cfg["device_no"], cfg["mqtt"], cfg["store"])
    heartbeat = Heartbeat(publisher, cfg.get("heartbeat_sec", 30))

    def report(events, reason):
        for detection in events:
            evidence = detector.source_evidence(detection)
            occurred = next(stamp for frame, stamp in times if frame == evidence)
            event = detector.payload(detection, publisher.device, cfg["elder_id"], occurred)
            publisher.report(event)
            logging.info("detection evidence=%d emit=%d reason=%s eventId=%s",
                         evidence, index, reason, event["eventId"])

    try:
        while not stop.is_set():
            detector = None
            processed = 0
            try:
                with source.open() as frames:
                    for index, captured, image in frames:
                        if detector is None:
                            height, width = image.shape[:2]
                            detector = StreamDetector(settings, cfg.get("roi"), source.fps,
                                                      width, height, stride)
                            times = deque(maxlen=detector.engine.history_frames + 3)
                        times.append((index, captured))
                        report(detector.feed(index, pose.predict(image)), "stream")
                        processed += 1
                        heartbeat.tick()
                    if source.is_file and detector and not stop.is_set():
                        report(detector.finish_file(), "file_eof")
                    logging.info("source end_mono=%.9f inferred=%d", time.perf_counter(), processed)
            except (cv2.error, OSError):
                if source.is_file:
                    raise
                logging.warning("Live source unavailable")
            if source.is_file:
                # Keep servicing a finite demo's offline outbox until broker recovery or shutdown.
                while publisher.store.oldest() and not stop.wait(0.1):
                    pass
                break
            if not stop.is_set():
                logging.warning("Live stream interrupted, reopening in 2 seconds")
                stop.wait(2)
    finally:
        heartbeat.close()
        publisher.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.yaml"))
    parser.add_argument("--downsample", type=int)
    args = parser.parse_args()
    cfg = load_settings(args.config)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(cfg, cfg.get("downsample", 1) if args.downsample is None else args.downsample, stop)


if __name__ == "__main__":
    main()
