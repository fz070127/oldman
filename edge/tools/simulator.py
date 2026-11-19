"""Publish falls from N independent simulated edge devices (UR Fall RGB or mock)."""
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_EXCEPTION
import logging
import random
import signal
import sys
import threading
import time
from pathlib import Path

import yaml

EDGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EDGE))
from detector_wrapper import ALGO, Pose, StreamDetector, make_event
from mqtt_client import Publisher


class VideoReplay:
    def __init__(self):
        sys.path.insert(0, str(ALGO / "scripts"))
        from extract_keypoints import read_image, sequence_frames
        from ur_manifest import read_manifest

        self.manifest = list(read_manifest().values())
        self.frames = sequence_frames
        self.read = read_image
        cfg = yaml.safe_load((EDGE / "config.yaml").read_text(encoding="utf-8"))
        self.settings = cfg["detector"].copy()
        self.settings["rules"] = EDGE / self.settings["rules"]
        self.roi = cfg.get("roi")
        self.pose = Pose(EDGE / self.settings["weights"], self.settings["cpu_threads"], self.settings["imgsz"])
        self.lock = threading.Lock()

    def event(self, device, elder, stop):
        # A negative sequence contributes no invented fall. Draw again to fill this device's interval.
        for row in random.sample(self.manifest, len(self.manifest)):
            files = self.frames(row)
            detector = StreamDetector(self.settings, self.roi, int(row["fps"]), 640, 480, 1)
            for frame, path in enumerate(files, 1):
                if stop.is_set():
                    return None
                image = self.read(path)
                with self.lock:
                    pose = self.pose.predict(image)
                events = detector.feed(frame, pose)
                if events:
                    break
            else:
                events = detector.finish_file()
            if events:
                logging.info("video device=%s seq=%s frame=%d", device, row["seq_id"], frame)
                return detector.payload(events[0], device, elder, time.time())
        return None


def simulate(number, args, replay, stop):
    device, elder = f"EDGE-{number:04d}", f"E{number:03d}"
    publisher = Publisher(device, dict(host=args.mqtt_host, port=args.mqtt_port),
                          args.store_dir / f"{device}.sqlite3")
    try:
        due = time.monotonic()
        while not stop.wait(max(0, due - time.monotonic())):
            started = time.monotonic()
            if replay:
                event = replay.event(device, elder, stop)
            else:
                level = random.choice(("P0", "P1"))
                features = dict(torsoAngle=round(random.uniform(5, 35), 2),
                                heightDrop=round(random.uniform(0.5, 0.8), 3),
                                stillDurationSec=2 if level == "P0" else 0,
                                trackId=1, aspectRatio=2.1, kpConf=0.7)
                event = make_event(device, elder, level, round(random.uniform(0.6, 0.95), 3),
                                   features, time.time())
            if event:
                publisher.report(event)
            due = started + args.interval
    finally:
        publisher.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--devices", type=int, default=5)
    parser.add_argument("--interval", type=float, default=300)
    parser.add_argument("--mqtt-host", default="localhost")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--store-dir", type=Path, default=EDGE / ".cache/simulator")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()
    if args.devices < 1 or args.interval <= 0:
        parser.error("devices and interval must be positive")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    replay = None if args.mock else VideoReplay()
    with ThreadPoolExecutor(max_workers=args.devices) as pool:
        jobs = [pool.submit(simulate, i + 1, args, replay, stop) for i in range(args.devices)]
        try:
            done, _ = wait(jobs, return_when=FIRST_EXCEPTION)
            for job in done:
                job.result()
        finally:
            stop.set()


if __name__ == "__main__":
    main()
