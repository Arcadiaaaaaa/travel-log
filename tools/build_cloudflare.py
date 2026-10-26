#!/usr/bin/env python3
"""只打包四个运行模块，避免把测试、虚拟环境或本地文件带到云端。"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".cloudflare-build"
TARGET.mkdir(exist_ok=True)
for path in TARGET.iterdir():
    if path.is_file():
        path.unlink()
for name in ("cloudflare_worker.py", "cloudflare_core.py", "cloudflare_crypto.py", "server.py"):
    shutil.copyfile(ROOT / name, TARGET / name)
print("Cloudflare 运行模块已准备（4个）；static/ 未修改。")
