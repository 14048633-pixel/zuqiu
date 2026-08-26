# -*- coding: utf-8 -*-
"""开盘盘口检查·定时守护（不依赖系统计划任务）
到点自动执行: python kickoff_check.py --league <L> --fetch
时间表写死在 SCHEDULE（北京时间），每 20 秒轮询一次。
已完成任务写入 kickoff_watchdog_done.json 防重复触发；重启后自动续跑未完成任务。
"""
import io
import json
import os
import subprocess
import sys
import time as _time
from datetime import datetime, timezone, timedelta

BJT = timezone(timedelta(hours=8))
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOG = os.path.join(HERE, "output", "kickoff_watchdog.log")
DONE = os.path.join(HERE, "output", "kickoff_watchdog_done.json")
YEAR = datetime.now(BJT).year

# (联赛, "MM-DD HH:MM", 说明) —— 北京时间
SCHEDULE = [
    ("J1",  "08-15 15:30", "J1 早盘观察(开赛前约1.5h)"),
    ("J1",  "08-15 16:30", "J1 开盘检查(开赛前30-60min, 主检)"),
    ("中超", "08-15 17:30", "中超 早盘观察(19:00开球前1.5h)"),
    ("中超", "08-15 18:25", "中超 开盘检查(19:00/19:35三场)"),
    ("中超", "08-15 19:25", "中超 临场检查(20:00两场)"),
    ("中超", "08-15 19:50", "中超 临场终检(20:00两场, 新5场注单)"),
    ("结算", "08-15 22:05", "中超结算(5注单 v2)", ["--league", "中超"]),
    ("结算", "08-16 06:00", "全量结算(J1/中超/欧系39场)"),
    ("结算", "08-17 09:00", "全量结算(西甲收尾)"),
    ("西甲", "08-15 20:00", "西甲 早盘观察"),
    ("西甲", "08-16 01:00", "西甲 阿拉维斯vs赫塔菲 赛前检查"),
    ("西甲", "08-16 03:00", "西甲 塞维利亚vs巴列卡诺 赛前检查"),
    ("西甲", "08-16 22:30", "西甲 桑坦德vs比利亚雷亚尔 赛前检查"),
    ("西甲", "08-17 00:30", "西甲 西班牙人vs莱万特 赛前检查"),
    ("西甲", "08-17 03:00", "西甲 塞尔塔vs奥萨苏纳 赛前检查"),
    ("瑞超", "08-15 22:30", "瑞超/挪超 临场复核(23:00-01:00开球)"),
    ("挪超", "08-15 22:30", "瑞超/挪超 临场复核(23:00-01:00开球)"),
    ("土超", "08-16 00:30", "土超 临场复核(00:00-02:30开球)"),
    ("英乙", "08-16 01:30", "英乙 临场复核(02:45-05:00开球)"),
    ("美职", "08-16 06:00", "美职 临场复核(06:00-10:00开球)"),
    ("巴甲", "08-16 06:00", "巴甲/阿甲 临场复核(03:00-07:15开球)"),
    ("阿甲", "08-16 06:00", "巴甲/阿甲 临场复核(03:00-07:15开球)"),
    ("台账", "08-16 08:00", "实盘台账回填(自动落账+统计)", ["--sync-ledger"]),
]


def log(msg):
    line = "[%s] %s" % (datetime.now(BJT).strftime("%m-%d %H:%M:%S"), msg)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)


def load_done():
    if os.path.exists(DONE):
        try:
            return set(json.load(io.open(DONE, encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_done(done):
    try:
        with io.open(DONE, "w", encoding="utf-8") as f:
            json.dump(sorted(done), f, ensure_ascii=False)
    except Exception as e:
        log("保存进度失败: %r" % e)


def selftest():
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(ROOT, "src", "odds"))
    try:
        from api_router import OddsApiRouter
        r = OddsApiRouter(base_dir=HERE, project_root=ROOT)
        if r.available():
            log("自检OK: 赔率key已加载(主链%d个%s)" % (len(r.keys), "+AS专用" if r.asian else ""))
        else:
            log("自检FAIL: 未加载到赔率key, 抓取将仅用现有快照")
    except Exception as e:
        log("自检异常: %r" % e)


def main():
    os.makedirs(os.path.join(HERE, "output"), exist_ok=True)
    done = load_done()
    selftest()
    log("守护进程启动, 定时任务共%d个, 已完成%d" % (len(SCHEDULE), len(done)))
    while True:
        now = datetime.now(BJT)
        for item in SCHEDULE:
            league, ts, label = item[0], item[1], item[2]
            extra = list(item[3]) if len(item) > 3 else []
            key = "%s|%s" % (league, ts)
            if key in done:
                continue
            target = datetime.strptime("%d-%s" % (YEAR, ts), "%Y-%m-%d %H:%M").replace(tzinfo=BJT)
            if now >= target:
                done.add(key)
                save_done(done)
                log("→ 触发: %s | %s" % (label, league))
                if league == "结算":
                    cmd = [sys.executable, os.path.join(HERE, "settle_batch.py"), "--fetch"] + extra
                elif league == "台账":
                    cmd = [sys.executable, os.path.join(HERE, "bet_ledger.py")] + extra
                else:
                    cmd = [sys.executable, os.path.join(HERE, "kickoff_check.py"),
                           "--league", league, "--fetch"]
                try:
                    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=900)
                    tail = (r.stdout or "").strip().splitlines()[-12:]
                    log("执行完毕(退出码%d):\n  %s" % (r.returncode, "\n  ".join(tail)))
                    if (r.stderr or "").strip():
                        log("stderr尾部: %s" % (r.stderr.strip()[-500:]))
                except Exception as e:
                    log("执行异常: %r" % e)
        _time.sleep(20)


if __name__ == "__main__":
    main()
