"""Encode one indexed sequence as an H.264 MP4 preview."""

import argparse
import shutil
import subprocess
from pathlib import Path

from ur_manifest import ALGO, indexed_frames, read_manifest, staged_output


def ffmpeg_executable():
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise ValueError("Install imageio[ffmpeg] or put ffmpeg on PATH.") from exc
    return imageio_ffmpeg.get_ffmpeg_exe()


def encode(row, output):
    if output.suffix.lower() != ".mp4":
        raise ValueError("The output filename must end in .mp4")
    frames = indexed_frames(ALGO / row["frame_dir"], row["seq_id"])
    if len(frames) != int(row["frame_count"]):
        raise ValueError("Frame count differs from the index. Inspect the source and rerun preparation.")
    ffmpeg = ffmpeg_executable()
    with staged_output(output) as staged:
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-xerror", "-y",
                   "-f", "image2pipe", "-c:v", "png", "-framerate", row["fps"], "-i", "pipe:0",
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(staged)]
        with subprocess.Popen(command, stdin=subprocess.PIPE) as encoder:
            with encoder.stdin as stream:
                for path in frames:
                    with path.open("rb") as source:
                        shutil.copyfileobj(source, stream)
            if encoder.wait() != 0:
                raise ValueError(f"FFmpeg failed with exit code {encoder.returncode}")
    print(f"{row['seq_id']}: {len(frames)} frames at {row['fps']} fps -> {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seq", required=True, help="Sequence ID, e.g. fall-01")
    parser.add_argument("--output", type=Path, help="Default: data/processed/clips/<seq>.mp4")
    args = parser.parse_args()
    try:
        rows = read_manifest()
        if args.seq not in rows:
            raise ValueError(f"Unknown sequence: {args.seq}")
        encode(rows[args.seq], args.output or ALGO / "data/processed/clips" / f"{args.seq}.mp4")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
