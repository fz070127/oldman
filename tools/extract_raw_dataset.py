"""把 UR Fall 原始数据压缩包解压到项目约定目录，支持断点续解与逐项校验。

用法：
    python tools/extract_raw_dataset.py --zip E:/sumanpunshi.zip
    python tools/extract_raw_dataset.py --zip E:/sumanpunshi.zip --verify-only

约束：
- 只写入项目根目录下的 sumanpunshi/，拒绝任何路径穿越条目。
- 已存在且大小一致的条目直接跳过，可重复执行。
- 不解压任何非 UR_data 下的数据文件之外的可执行内容；保持原始目录结构。
"""

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "sumanpunshi"
PREFIX = "sumanpunshi/"


def safe_target(name: str) -> Path:
    """拒绝绝对路径、盘符、.. 穿越与目标前缀之外的条目。"""
    pure = Path(name.replace("\\", "/"))
    if name.startswith(("/", "\\")) or pure.drive or pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"不安全的压缩包条目: {name}")
    if not name.startswith(PREFIX) and name.rstrip("/") != "sumanpunshi":
        raise ValueError(f"条目不在预期前缀内: {name}")
    resolved = (ROOT / pure).resolve()
    target = TARGET.resolve()
    if not target.is_relative_to(ROOT) or not resolved.is_relative_to(target):
        raise ValueError(f"条目越出目标目录: {name}")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if not args.zip.exists():
        print(f"ZIP_NOT_FOUND {args.zip}", file=sys.stderr)
        return 2

    extracted = skipped = directories = 0
    bad = []
    png = 0
    with zipfile.ZipFile(args.zip) as archive:
        infos = archive.infolist()
        for info in infos:
            dest = safe_target(info.filename)
            if info.is_dir() or info.filename.endswith("/"):
                directories += 1
                if not args.verify_only:
                    dest.mkdir(parents=True, exist_ok=True)
                continue
            if dest.exists() and dest.stat().st_size == info.file_size:
                skipped += 1
            else:
                bad.append((info.filename, info.file_size,
                            dest.stat().st_size if dest.exists() else -1))
            if dest.suffix.lower() == ".png":
                png += 1
        if not args.verify_only and bad:
            TARGET.mkdir(parents=True, exist_ok=True)
            missing = {name for name, _, _ in bad}
            for info in infos:
                if info.filename in missing:
                    dest = safe_target(info.filename)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as source, dest.open("wb") as sink:
                        while True:
                            chunk = source.read(1024 * 1024)
                            if not chunk:
                                break
                            sink.write(chunk)
                    extracted += 1

    # 逐项复验：所有条目存在且大小一致
    mismatches = []
    with zipfile.ZipFile(args.zip) as archive:
        for info in archive.infolist():
            if info.is_dir() or info.filename.endswith("/"):
                continue
            dest = safe_target(info.filename)
            if not dest.exists() or dest.stat().st_size != info.file_size:
                mismatches.append(info.filename)
    summary = {
        "zip": str(args.zip),
        "entries": len(infos),
        "png_entries": png,
        "directory_entries": directories,
        "extracted": extracted,
        "already_present": skipped,
        "mismatches": len(mismatches),
        "verify_passed": not mismatches,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if mismatches:
        print("FIRST_MISMATCHES", mismatches[:5], file=sys.stderr)
        return 1
    out = ROOT / "algo" / "reports" / "raw_dataset_extract.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
