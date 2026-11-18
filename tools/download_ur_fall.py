"""UR Fall 缺失数据下载器（cam1 RGB / 深度 / 加速度 / 对齐表 / 视频）

设计要点
- 按队列顺序下载，不并发：实测该服务器并发会更慢（约 370 KB/s 单连接，
  并发 3 路降到 15-60 KB/s），且不稳定
- 断点续传：.part 文件 + Range 请求，中断后重跑只补缺的部分
- 失败重试：每文件最多 6 次，指数退避；服务器偶发直接断连（curl exit 52）
- 完整性校验：用服务器 HEAD 返回的 Content-Length 比对，不一致视为失败
- 幂等：已完整下载的文件跳过

用法
    py -I tools/download_ur_fall.py                 # 默认下载 tier 1~4（不含 mp4）
    py -I tools/download_ur_fall.py --tiers 1,2,3   # 只下指定层
    py -I tools/download_ur_fall.py --list          # 只列清单不下载
    py -I tools/download_ur_fall.py --verify        # 只校验已下载文件

层级（按价值排序）
    1  acc.csv / data.csv   对齐表与加速度，共 140 个文件，合计约 2 MB     → 秒级完成
    2  mp4                  已合成视频，共 100 个，约 130 MB              → 备份用
    3  cam1-rgb.zip         天花板机位的 RGB，30 段，约 1.8 GB           → 第二机位
    4  cam0-d.zip           正对机位深度图，70 段，约 2.2 GB             → 无光通道
    5  cam1-d.zip           天花板机位深度图，30 段，约 1.3 GB           → 可选
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://fenix.ur.edu.pl/~mkepski/ds/data/"
MANIFEST = Path(__file__).with_name("ur_fall_manifest.tsv")
DEST = Path(__file__).resolve().parents[1] / "sumanpunshi" / "ur-fall-extra"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
RETRIES = 6


def load_manifest() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        tier, name = line.split("\t", 1)
        rows.append((tier, name.strip()))
    return rows


def remote_size(name: str) -> int | None:
    """用 HEAD 取文件大小，失败返回 None（不阻断下载）。"""
    req = urllib.request.Request(BASE + name, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            length = r.headers.get("Content-Length")
            return int(length) if length else None
    except Exception:
        return None


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}GB"


def download(name: str, dest_dir: Path) -> tuple[bool, str]:
    """带续传与重试的单文件下载。返回 (成功, 说明)。"""
    target = dest_dir / name
    part = target.with_suffix(target.suffix + ".part")
    target.parent.mkdir(parents=True, exist_ok=True)

    expected = remote_size(name)
    if expected is not None and target.exists() and target.stat().st_size == expected:
        return True, "已存在"

    last_err = ""
    for attempt in range(1, RETRIES + 1):
        have = part.stat().st_size if part.exists() else 0
        if expected is not None and have == expected and have > 0:
            part.replace(target)
            return True, "续传完成"

        headers = {"User-Agent": UA}
        if have:
            headers["Range"] = f"bytes={have}-"
        req = urllib.request.Request(BASE + name, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                mode = "ab" if have and r.status == 206 else "wb"
                if mode == "wb":
                    have = 0
                total = expected or 0
                t0 = time.time()
                with open(part, mode) as f:
                    while True:
                        chunk = r.read(256 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        have += len(chunk)
                        if total and have % (4 * 1024 * 1024) < 256 * 1024:
                            speed = have / max(time.time() - t0, 0.1)
                            pct = have * 100 / total
                            print(
                                f"\r    {name}  {pct:5.1f}%  {human(have)}/{human(total)}"
                                f"  {human(speed)}/s   ",
                                end="",
                                flush=True,
                            )

            size = part.stat().st_size
            if expected is not None and size != expected:
                last_err = f"大小不符 {size}/{expected}"
                time.sleep(2 * attempt)
                continue
            part.replace(target)
            print(f"\r    {name}  完成 {human(size)}" + " " * 30)
            return True, "下载完成"
        except urllib.error.HTTPError as e:
            if e.code == 416 and expected and have == expected:
                part.replace(target)
                return True, "已完整"
            last_err = f"HTTP {e.code}"
        except Exception as e:  # 连接中断、超时等
            last_err = type(e).__name__
        time.sleep(min(2 * attempt, 15))

    return False, f"失败（{last_err}）"


def verify(dest_dir: Path) -> int:
    """校验已下载文件，返回缺失/损坏数量。"""
    bad = 0
    rows = load_manifest()
    for _, name in rows:
        target = dest_dir / name
        if not target.exists():
            print(f"  缺失  {name}")
            bad += 1
            continue
        expected = remote_size(name)
        if expected is not None and target.stat().st_size != expected:
            print(f"  损坏  {name}  {target.stat().st_size}/{expected}")
            bad += 1
    print(f"\n校验完成：{len(rows) - bad}/{len(rows)} 正常")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tiers", default="1,2,3,4", help="要下载的层级，逗号分隔，默认 1,2,3,4")
    ap.add_argument("--list", action="store_true", help="只列出清单")
    ap.add_argument("--verify", action="store_true", help="只校验")
    ap.add_argument("--dest", default=str(DEST), help="目标目录")
    args = ap.parse_args()

    dest_dir = Path(args.dest)
    rows = load_manifest()

    if args.verify:
        return 1 if verify(dest_dir) else 0

    if args.list:
        from collections import Counter

        c = Counter(t for t, _ in rows)
        for tier in sorted(c):
            print(f"  tier {tier}: {c[tier]} 个文件")
        print(f"  合计 {len(rows)} 个")
        return 0

    wanted = {t.strip() for t in args.tiers.split(",") if t.strip()}
    # 清单里的层级写作 "1_sync"，允许只写数字
    todo = [(t, n) for t, n in rows if t in wanted or t.split("_")[0] in wanted]
    if not todo:
        print(f"没有匹配的层级：{wanted}")
        return 2

    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"目标目录：{dest_dir}")
    print(f"文件数：{len(todo)}")
    print("提示：服务器约 370 KB/s 且不稳定，深度图层可能需要数小时。可随时 Ctrl+C，重跑会续传。\n")

    done = skipped = failed = 0
    failures: list[str] = []
    t_start = time.time()
    for i, (tier, name) in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] tier{tier} {name}")
        ok, msg = download(name, dest_dir)
        if ok:
            if msg == "已存在":
                skipped += 1
            else:
                done += 1
        else:
            failed += 1
            failures.append(name)
            print(f"    跳过：{msg}")
        if i % 20 == 0:
            elapsed = time.time() - t_start
            print(f"    ---- 进度 {i}/{len(todo)}，已用时 {elapsed / 60:.0f} 分钟 ----")

    print(f"\n完成：新下载 {done}，跳过 {skipped}，失败 {failed}")
    if failures:
        print("失败清单（重跑本脚本会自动续传）：")
        for f in failures:
            print(f"  {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())