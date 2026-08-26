# -*- coding: utf-8 -*-
"""自动虚拟结算守护: 轮询台账待结算, 只结算"活跃窗口"联赛, 全部完赛后自动跑 phase_review 出命中率
用法:
  python paper_watchdog.py --key <the-odds-api key> --interval 20 --max-rounds 40
"""
import argparse, csv, io, json, os, subprocess, sys, time
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "analysis_records", "bet_ledger.csv")
ARCH = os.path.join(HERE, "analysis_records", "20260815_scan_upcoming.json")
BJT = timezone(timedelta(hours=8))

ACTIVE_WINDOW_BEFORE = timedelta(minutes=120)   # 开球前120分钟开始拉该联赛
ACTIVE_WINDOW_AFTER = timedelta(minutes=170)    # 开球后170分钟仍算活跃(等补时完赛)


def load_pending():
    rows = []
    if os.path.exists(LEDGER):
        with io.open(LEDGER, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("status") == "待结算":
                    rows.append(r)
    return rows


def norm(s):
    return "".join(c.lower() for c in s if c.isalnum())


def load_ct_map():
    m = {}
    if os.path.exists(ARCH):
        d = json.load(io.open(ARCH, encoding="utf-8"))
        for x in d.get("matches", []):
            m[(x.get("league"), norm(x.get("home", "")), norm(x.get("away", "")))] = x.get("ct")
    return m


FINISH_BUFFER = timedelta(minutes=115)   # 开球+115min 预计完赛
WINDOW = timedelta(minutes=20)       # 完赛前后20分钟窗口内拉


def active_leagues(now, pending, ct_map):
    """按预计完赛时间调度: 只在"预计完赛±20min"或"早该完赛仍未结"时拉对应联赛
    无开球时间的注单保险拉该联赛; 该拉的才拉, 不每30分钟全量扫。"""
    due = set()
    for r in pending:
        ct = ct_map.get((r.get("league"), norm(r.get("home", "")), norm(r.get("away", ""))))
        if not ct:
            due.add(r.get("league"))
            continue
        try:
            ko = datetime.fromisoformat(ct.replace("Z", "+00:00"))
        except Exception:
            due.add(r.get("league"))
            continue
        done_at = ko + FINISH_BUFFER
        if done_at - WINDOW <= now <= done_at + WINDOW:
            due.add(r.get("league"))
        elif now > done_at + WINDOW:
            # 早该完赛仍未结 -> 补拉(防延迟/漏结)
            due.add(r.get("league"))
    return due


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", required=True)
    ap.add_argument("--key2", default="")
    ap.add_argument("--interval", type=int, default=10)
    ap.add_argument("--max-rounds", type=int, default=40)
    args = ap.parse_args()
    ct_map = load_ct_map()
    log = os.path.join(HERE, "analysis_records", "paper_watchdog.log")
    def L(msg):
        line = "%s %s" % (datetime.now(BJT).strftime("%m-%d %H:%M"), msg)
        print(line)
        with io.open(log, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    L("守护启动 key=%s... interval=%dmin max_rounds=%d" % (args.key[:8], args.interval, args.max_rounds))
    for rnd in range(1, args.max_rounds + 1):
        now = datetime.now(timezone.utc)
        pend = load_pending()
        if not pend:
            L("全部待结算已结清 -> 跑阶段复盘")
            subprocess.run([sys.executable, "-X", "utf8", "phase_review.py"], cwd=HERE)
            L("完成")
            return
        leagues = active_leagues(now, pend, ct_map)
        key_now = args.key2 if (rnd % 2 == 0 and args.key2) else args.key
        if leagues:
            L("第%d轮: 待结算%d | 应拉联赛 %d 个: %s | key=%s" % (rnd, len(pend), len(leagues), ",".join(sorted(leagues)), key_now[:8]))
            try:
                p = subprocess.run([sys.executable, "-X", "utf8", "paper_settle.py", "--league", ",".join(sorted(leagues)), "--key", key_now],
                                   cwd=HERE, capture_output=True, text=True, encoding="utf-8", timeout=300)
                tail = (p.stdout or "").strip().splitlines()
                for line in tail[-5:]:
                    L("  " + line[:150])
            except Exception as e:
                L("  结算异常 %r" % (e,))
        else:
            L("第%d轮: 待结算%d | 当前无临近完赛场次, 跳过(不浪费请求)" % (rnd, len(pend)))
        time.sleep(args.interval * 60)
    L("达到最大轮数, 仍有待结算, 人工补跑 paper_settle.py")


if __name__ == "__main__":
    main()
