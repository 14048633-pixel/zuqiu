# -*- coding: utf-8 -*-
"""后台启动 settle_final (一次性, 最后一场完赛后自动结算+复盘)"""
import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
k1 = "1e6c4897f23261d77dabcda61fbae37e"
cmd = [sys.executable, "-X", "utf8", "settle_final.py", "--buffer-min", "15", "--key", k1]
DETACHED = 0x00000008 | 0x00000200
p = subprocess.Popen(cmd, cwd=HERE, creationflags=DETACHED,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
print("settle_final pid:", p.pid)
