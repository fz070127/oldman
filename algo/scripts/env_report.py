"""B1: 记录训练环境的版本核对清单，落盘为 reports/environment.md 与 json。

路线 B1 要求"记录版本与配置"，本脚本只读取真实环境，不做任何推断。
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

ALGO = Path(__file__).resolve().parents[1]
REPORTS = ALGO / "reports"


def main():
    import cv2
    import numpy as np
    import torch
    import ultralytics

    gpu = {
        "cuda_available": torch.cuda.is_available(),
        "torch_cuda_version": torch.version.cuda,
        "device_count": torch.cuda.device_count(),
        "devices": [],
    }
    for index in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(index)
        gpu["devices"].append({
            "index": index,
            "name": props.name,
            "capability": f"{props.major}.{props.minor}",
            "total_memory_gb": round(props.total_memory / 1024 ** 3, 2),
        })
    if gpu["cuda_available"]:
        a = torch.randn(512, 512, device="cuda")
        torch.cuda.synchronize()
        gpu["matmul_ok"] = bool(torch.isfinite(a @ a).all().item())
    else:
        gpu["matmul_ok"] = False

    record = {
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torchvision": _version("torchvision"),
        "numpy": np.__version__,
        "opencv": cv2.__version__,
        "ultralytics": ultralytics.__version__,
        "gpu": gpu,
        "pip_freeze": _pip_freeze(),
        "verified_with": "scripts/env_report.py（全部字段为运行时实测）",
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "environment.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# B1 · 训练环境核对清单",
        "",
        "由 `algo/scripts/env_report.py` 运行时实测生成，非人工填写。",
        "",
        "| 项目 | 值 |",
        "|---|---|",
        f"| Python | {record['python']} |",
        f"| 解释器 | `{record['python_executable']}` |",
        f"| PyTorch | {record['torch']} |",
        f"| torchvision | {record['torchvision']} |",
        f"| torch CUDA 构建 | {gpu['torch_cuda_version']} |",
        f"| CUDA 可用 | {gpu['cuda_available']} |",
        f"| GPU | {', '.join(d['name'] for d in gpu['devices']) or '无'} |",
        f"| 算力 (sm) | {', '.join(d['capability'] for d in gpu['devices']) or '-'} |",
        f"| 显存 | {', '.join(str(d['total_memory_gb']) + ' GB' for d in gpu['devices']) or '-'} |",
        f"| GPU 矩阵乘自检 | {gpu['matmul_ok']} |",
        f"| ultralytics | {record['ultralytics']} |",
        f"| OpenCV | {record['opencv']} |",
        f"| NumPy | {record['numpy']} |",
        "",
        "## 说明",
        "",
        "- 环境曾出现 miniconda 解释器加载 `c10.dll` 报 WinError 1114（DLL 初始化例程失败），",
        "  在多个 venv、纯净 PATH 下均复现，最终改用官方 CPython 3.12 解释器后消失；",
        "  该结论为实测排除，非版本推测。",
        "- torch 与 torchvision 由阿里云 PyTorch 镜像下载的 cu128 轮子离线安装（避免官方源反复中断）。",
        "",
        "## pip freeze",
        "",
        "```",
        *record["pip_freeze"],
        "```",
    ]
    (REPORTS / "environment.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({k: v for k, v in record.items() if k != "pip_freeze"},
                     ensure_ascii=False, indent=2))


def _version(name):
    try:
        module = __import__(name)
        return getattr(module, "__version__", "unknown")
    except Exception:
        return "not installed"


def _pip_freeze():
    result = subprocess.run([sys.executable, "-m", "pip", "freeze"],
                            capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line.strip()]


if __name__ == "__main__":
    main()
