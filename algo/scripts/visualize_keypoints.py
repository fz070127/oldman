"""从已保存的姿态数组绘制骨架，输出逐帧对齐的 MP4。"""

import argparse
import subprocess
from pathlib import Path

import cv2
import numpy as np

from extract_keypoints import OUT, read_image, sequence_frames, validate
from preview import ffmpeg_executable
from ur_manifest import read_manifest, staged_output

EDGES = ((0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (7, 9), (6, 8),
         (8, 10), (5, 11), (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seq", required=True, choices=read_manifest().keys())
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    row = read_manifest()[args.seq]
    paths = sequence_frames(row)
    archive = OUT / f"{args.seq}.npz"
    validate(archive, args.seq, len(paths))
    output = args.output or OUT.parent / "overlays" / f"{args.seq}.mp4"
    with np.load(archive, allow_pickle=False) as a, staged_output(output) as tmp:
        xy, conf, boxes, scores = (a[key] for key in ("kpts", "kpts_conf", "boxes", "scores"))
        cmd = [ffmpeg_executable(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s", "640x480", "-r", "30", "-i", "pipe:0", "-c:v", "libx264", "-pix_fmt",
               "yuv420p", "-movflags", "+faststart", str(tmp)]
        with subprocess.Popen(cmd, stdin=subprocess.PIPE) as encoder:
            with encoder.stdin as stream:
                for i, path in enumerate(paths):
                    im = read_image(path)
                    for slot, color in enumerate(((0, 220, 255), (255, 180, 20))):
                        if scores[i, slot] == 0:
                            continue
                        points = xy[i, slot].round().astype(int)
                        visible = conf[i, slot] >= 0.3
                        x1, y1, x2, y2 = boxes[i, slot].round().astype(int)
                        cv2.rectangle(im, (x1, y1), (x2, y2), color, 1)
                        for start, end in EDGES:
                            if visible[start] and visible[end]:
                                cv2.line(im, tuple(points[start]), tuple(points[end]), color, 2)
                        for point in points[visible]:
                            cv2.circle(im, tuple(point), 3, color, -1)
                    cv2.putText(im, f"{args.seq} #{i+1}", (10, 25),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
                    stream.write(im.tobytes())
            if encoder.wait():
                raise RuntimeError(f"视频编码失败: {output}")
    print(f"{output} ({len(paths)} frames)")


if __name__ == "__main__":
    main()
