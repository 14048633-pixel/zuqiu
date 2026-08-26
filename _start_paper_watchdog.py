# -*- coding: utf-8 -*-
"""后台启动 paper_watchdog (避免 PowerShell 参数拼接坑)"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
# 读 .env 取主链key
k1 = "1e6c4897f23261d77dabcda61fbae37e"  # the-odds-api 新key
k2 = ""
with open(os.path.join(HERE, ".env"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("ODDS_API_KEY_1="):
            k2 = line.split("=", 1)[1].split("#")[0].strip()
cmd = [sys.executable, "-X", "utf8", "paper_watchdog.py", "--key", k1, "--key2", k2,
       "--interval", "30", "--max-rounds", "24"]
DETACHED = 0x00000008 | 0x00000200
p = subprocess.Popen(cmd, cwd=HERE, creationflags=DETACHED,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL)
print("paper_watchdog pid:", p.pid, "key2:", k2[:8])
