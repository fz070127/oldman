"""Reproduce A5 val/test and six paced MP4-to-MQTT measurements."""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from statistics import mean
from uuid import uuid4

import numpy as np
import paho.mqtt.client as mqtt
import psutil
import yaml

EDGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EDGE))
from agent import load_settings
from detector_wrapper import ALGO, StreamDetector

sys.path.insert(0, str(ALGO / "scripts"))
from preview import ffmpeg_executable
from ur_manifest import indexed_frames, read_manifest

SEQUENCES = ("fall-01", "fall-05", "fall-09", "fall-06", "fall-10", "fall-02")


def evaluate(cfg, hold_sec):
    manifest = read_manifest()
    for split in ("val", "test"):
        with (ALGO / "data/splits" / f"{split}.csv").open(encoding="utf-8-sig") as f:
            members = list(csv.DictReader(f))
        for window, stride in ((3, 1), (2, 1), (3, 2), (2, 2)):
            hits, false, p0 = [], [], []
            for row in members:
                seq = row["seq_id"]
                path = ALGO / "data/processed/keypoints" / f"{seq}.npz"
                with np.load(path, allow_pickle=False) as data:
                    arrays = [data[k] for k in ("boxes", "kpts", "kpts_conf", "scores", "n_people")]
                n = len(arrays[0])
                fps = int(manifest[seq]["fps"])
                detector = StreamDetector(dict(cfg["detector"], motion_window_sec=window),
                                          cfg.get("roi"), fps, 640, 480, stride)
                levels = set()
                for i in range(0, n + hold_sec * fps, stride):
                    events = detector.feed(i + 1, [a[min(i, n - 1)] for a in arrays])
                    levels.update(d["level"] for d in events)
                if not hold_sec:
                    levels.update(d["level"] for d in detector.finish_file())
                if levels:
                    (hits if row["label"] == "fall" else false).append(seq)
                if "P0" in levels:
                    p0.append(seq)
            print(json.dumps(dict(split=split, window=window, stride=stride, hold_sec=hold_sec, hits=hits,
                                  false=false, p0=p0)), flush=True)


def prepare(row, output):
    frames = indexed_frames(ALGO / row["frame_dir"], row["seq_id"])
    cmd = [ffmpeg_executable(), "-loglevel", "error", "-y", "-framerate", row["fps"],
           "-f", "image2pipe", "-c:v", "png", "-i", "pipe:0", "-vf",
           "tpad=stop_mode=clone:stop_duration=4", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "0", "-pix_fmt", "yuv444p", str(output)]
    with subprocess.Popen(cmd, stdin=subprocess.PIPE) as proc:
        with proc.stdin as pipe:
            for frame in frames:
                pipe.write(frame.read_bytes())
        if proc.wait():
            raise RuntimeError("ffmpeg failed")


def video(cfg, args, work):
    manifest = read_manifest()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    subscribed = threading.Event()
    arrival = threading.Condition()
    messages = []

    def received(client, userdata, msg):
        stamp = time.perf_counter()
        with arrival:
            messages.append((stamp, json.loads(msg.payload)))
            arrival.notify()

    client.on_message = received
    client.on_subscribe = lambda *_: subscribed.set()
    client.on_connect = lambda c, *_: c.subscribe("edge/A5-BENCH/event", qos=1)
    client.connect(args.mqtt_host, args.mqtt_port)
    client.loop_start()
    try:
        if not subscribed.wait(10):
            raise RuntimeError("MQTT subscription timed out")
        cfg.update(device_no="A5-BENCH", store=str(work / "events.db"), heartbeat_sec=1)
        cfg["mqtt"].update(host=args.mqtt_host, port=args.mqtt_port, topic_prefix="edge")
        for seq in args.seq:
            row = manifest[seq]
            clip = work / f"{seq}.mp4"
            prepare(row, clip)
            cfg["video_file"] = str(clip)
            path = work / "bench.yaml"
            path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
            with arrival:
                messages.clear()
            log = work / f"{seq}.log"
            cmd = [sys.executable, str(EDGE / "agent.py"), "--config", str(path),
                   "--downsample", str(args.downsample)]
            with log.open("w", encoding="utf-8") as out, subprocess.Popen(
                    cmd, stdout=out, stderr=subprocess.STDOUT,
                    env=dict(os.environ, PYTHONIOENCODING="utf-8")) as proc:
                handle = psutil.Process(proc.pid)
                usage = []
                previous_time = time.perf_counter()
                previous_cpu = 0
                psutil.cpu_percent()
                while proc.poll() is None:
                    time.sleep(0.5)
                    if proc.poll() is None:
                        # On Windows the venv launcher starts a child Python interpreter.
                        try:
                            family = [handle, *handle.children(recursive=True)]
                        except psutil.NoSuchProcess:
                            break
                        cpu = rss = 0
                        for p in family:
                            try:
                                times = p.cpu_times()
                                cpu += times.user + times.system
                                rss += p.memory_info().rss
                            except psutil.NoSuchProcess:
                                continue
                        now = time.perf_counter()
                        percent = 100 * (cpu - previous_cpu) / (now - previous_time) / psutil.cpu_count()
                        usage.append((now, max(0, percent), psutil.cpu_percent(), rss / 2**20))
                        previous_time, previous_cpu = now, cpu
            content = log.read_text(encoding="utf-8")
            if proc.returncode:
                raise RuntimeError(content)
            origin = float(re.search(r"origin_mono=([\d.]+)", content)[1])
            end = re.search(r"source end_mono=([\d.]+) inferred=(\d+)", content)
            ended, inferred = float(end[1]), int(end[2])
            usage = [u for u in usage if origin + 0.5 <= u[0] <= ended]
            onset = int(row["fall_onset"])
            result = dict(seq=seq, onset=onset, fps=round(inferred / (ended - origin), 2),
                          process_cpu=round(mean(u[1] for u in usage), 2),
                          system_cpu=round(mean(u[2] for u in usage), 2),
                          system_cpu_max=max(u[2] for u in usage),
                          peak_rss_mib=round(max(u[3] for u in usage), 2))
            sent_ids = set(re.findall(r"MQTT PUBACK eventId=([\w-]+)", content))
            if sent_ids:
                with arrival:
                    if not arrival.wait_for(lambda: sent_ids.issubset(
                            {event["eventId"] for _, event in messages}), timeout=5):
                        raise RuntimeError(f"{seq}: acknowledged event missing at subscriber")
                    stamp, event = next(m for m in messages if m[1]["eventId"] in sent_ids)
                m = re.search(r"detection evidence=(\d+) emit=(\d+) reason=(\w+) eventId=" +
                              re.escape(event["eventId"]), content)
                ack = re.search(r"MQTT PUBACK eventId=" + re.escape(event["eventId"]) +
                                r" publish_mono=([\d.]+)", content)
                start = origin + (onset - 1) / int(row["fps"])
                result.update(evidence=int(m[1]), emit=int(m[2]), reason=m[3], payload=event,
                              publish_sec=round(float(ack[1]) - start, 4),
                              subscriber_sec=round(stamp - start, 4))
            print(json.dumps(result, ensure_ascii=True), flush=True)
    finally:
        client.disconnect()
        client.loop_stop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["splits", "video"])
    parser.add_argument("--mqtt-host", default="localhost")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--downsample", type=int, default=1)
    parser.add_argument("--seq", nargs="+", choices=SEQUENCES, default=SEQUENCES,
                        help="video sequences (defaults to all six)")
    parser.add_argument("--hold-sec", type=int, choices=(0, 4), default=4,
                        help="splits only: 0 uses A4 file EOF, 4 simulates a stationary tail")
    args = parser.parse_args()
    cfg = load_settings(EDGE / "config.yaml")
    if args.mode == "splits":
        evaluate(cfg, args.hold_sec)
    else:
        directory = EDGE / ".cache/bench" / uuid4().hex
        directory.mkdir(parents=True)
        print(f"Video clips and agent logs: {directory}", file=sys.stderr)
        video(cfg, args, directory)


if __name__ == "__main__":
    main()
