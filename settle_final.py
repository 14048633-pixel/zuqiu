# -*- coding: utf-8 -*-
"""一次性最终结算: 睡到最后一场预计完赛+缓冲, 自动全量结算 -> 复盘 -> 命中率报告
用法: python settle_final.py [--buffer-min 15] [--key <the-odds-api key>]
"""
import argparse, csv, io, json, os, subprocess, sys, time
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "analysis_records", "bet_ledger.csv")
ARCH = os.path.join(HERE, "analysis_records", "20260815_scan_upcoming.json")
BJT = timezone(timedelta(hours=8))
LOG = os.path.join(HERE, "analysis_records", "settle_final.log")


def norm(s):
    return "".join(c.lower() for c in s if c.isalnum())


def L(msg):
    line = "%s %s" % (datetime.now(BJT).strftime("%m-%d %H:%M"), msg)
    print(line)
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def last_finish():
    ct_map = {}
    if os.path.exists(ARCH):
        d = json.load(io.open(ARCH, encoding="utf-8"))
        for m in d.get("matches", []):
            ct_map[(m.get("league"), norm(m.get("home", "")), norm(m.get("away", "")))] = m.get("ct")
    rows = list(csv.DictReader(io.open(LEDGER, encoding="utf-8")))
    pend = [r for r in rows if r.get("status") == "待结算"]
    ends = []
    for r in pend:
        ct = ct_map.get((r.get("league"), norm(r.get("home", "")), norm(r.get("away", ""))))
        if ct:
            try:
                ko = datetime.fromisoformat(ct.replace("Z", "+00:00"))
                ends.append(ko + timedelta(minutes=115))
            except Exception:
                pass
    if not ends:
        return None, pend
    return max(ends), pend


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--buffer-min", type=int, default=15)
    ap.add_argument("--key", required=True)
    args = ap.parse_args()
    last, pend = last_finish()
    if last is None:
        L("无待结算注单, 直接复盘")
        subprocess.run([sys.executable, "-X", "utf8", "phase_review.py"], cwd=HERE)
        return
    target = last + timedelta(minutes=args.buffer_min)
    now = datetime.now(timezone.utc)
    wait = (target - now).total_seconds()
    L("待结算 %d 场 | 最后一场预计完赛(北京) %s | +%dmin缓冲 -> %s 结算" % (
        len(pend), last.astimezone(BJT).strftime("%m-%d %H:%M"), args.buffer_min,
        target.astimezone(BJT).strftime("%m-%d %H:%M")))
    if wait > 0:
        L("等待 %.1f 小时后自动结算..." % (wait / 3600))
        time.sleep(wait)
    # 全量结算(所有联赛)
    L("开始全量结算...")
    p = subprocess.run([sys.executable, "-X", "utf8", "paper_settle.py", "--key", args.key],
                       cwd=HERE, capture_output=True, text=True, encoding="utf-8", timeout=600)
    for line in (p.stdout or "").strip().splitlines()[-8:]:
        L("  " + line[:150])
    if p.returncode != 0:
        L("结算进程异常 rc=%s stderr=%s" % (p.returncode, (p.stderr or "")[:300]))
    # 复盘
    L("生成阶段复盘报告...")
    subprocess.run([sys.executable, "-X", "utf8", "phase_review.py"], cwd=HERE)
    L("全部完成")


if __name__ == "__main__":
    main()
