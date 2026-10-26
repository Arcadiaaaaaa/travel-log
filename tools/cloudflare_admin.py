#!/usr/bin/env python3
"""在用户终端安全初始化或修改 Cloudflare 登录密码，不打印或保存秘密。"""
import getpass
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import server


def main():
    if not sys.stdin.isatty():
        sys.exit("请在本机交互终端运行此命令；密码不能写进命令参数或日志。")
    first = getpass.getpass("新的旅行记录密码：")
    if len(first) < server.MIN_PASSWORD_LEN:
        sys.exit(f"密码至少 {server.MIN_PASSWORD_LEN} 位")
    if first != getpass.getpass("再输入一次："):
        sys.exit("两次输入的密码不一致")
    # 只通过标准输入发送PBKDF2哈希；明文密码不离开本机进程。
    hashed = server.hash_password(first)
    first = None
    env = {**os.environ,"WRANGLER_SEND_METRICS":"false","WRANGLER_LOG":"error"}
    result = subprocess.run([str(ROOT/"node_modules/.bin/wrangler"),"secret","put","PASSWORD_HASH"],
                            input=hashed+"\n",text=True,cwd=ROOT,env=env,capture_output=True)
    hashed = None
    if result.returncode:
        sys.exit("密码配置失败。请先运行 Wrangler whoami 检查登录，然后重试；为避免泄露秘密，此处不输出原始工具日志。")
    print("密码已配置，旧 Cookie 会话和 App 令牌已失效。")


if __name__ == "__main__":
    main()
