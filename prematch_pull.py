# -*- coding: utf-8 -*-
"""赛前30分钟定点拉取: 每场比赛开赛前30分钟窗口拉一次最新盘口
用法: python prematch_pull.py [--id <bsd_event_id>]   (由每5分钟计划任务调用)
输出: analysis_records/prematch_snap_{id}_{ts}.json
"""
import sys, io, os, json, time, urllib.request
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
STATE = os.path.join(ROOT, "analysis_records", "prematch_pull_state.json")
OUTDIR = os.path.join(ROOT, "analysis_records", "prematch_snap")
LOG = os.path.join(ROOT, "analysis_records", "prematch_pull.log")
BJT = timezone(timedelta(hours=8))
WINDOW_MIN, WINDOW_MAX = 20, 40   # 开赛前20~40分钟窗口内触发(30分钟前后容忍)

env = {}
for line in io.open(ROOT + r"\.env", encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line: continue
    k, v = line.split("=", 1)
    env[k.strip()] = v.split("#")[0].strip()
BTOK = env.get("BZZOIRO_API_KEY", "").strip('"').strip("'")

def log(msg):
    line = "%s %s" % (datetime.now(BJT).strftime("%m-%d %H:%M:%S"), msg)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f: f.write(line + "\n")
    except Exception: pass
    print(line)

def bsd_get(path):
    for i in range(3):
        try:
            req = urllib.request.Request("https://sports.bzzoiro.com/api/v2" + path,
                                         headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + BTOK})
            return json.load(urllib.request.urlopen(req, timeout=40))
        except Exception:
            time.sleep(2)
    return {"__err__": "fetch failed"}

def load_targets():
    """读最新 scan48h 赛程(按修改时间取新), 旧 key46 仅兜底. 2026-08-22 修复: 此前硬编码 key46_20260818_2307.json 过期不更新."""
    import glob
    src = None
    for f in sorted(glob.glob(ROOT + r"\analysis_records\scan??h_*.json"), key=os.path.getmtime, reverse=True):
        bn = os.path.basename(f)
        if "final" in bn or "clean" in bn:
            continue
        try:
            d = json.load(io.open(f, encoding="utf-8"))
            ms = d.get("matches") or []
            if ms:
                src = (bn, ms)
                break
        except Exception:
            continue
    if src is None:
        d = json.load(io.open(ROOT + r"\analysis_records\key46_20260818_2307.json", encoding="utf-8"))
        src = ("key46_20260818_2307.json", d.get("results") or [])
    log("load_targets: %s (%d 场)" % (src[0], len(src[1])))
    out = []
    for r in src[1]:
        try:
            dd, tt = r["kickoff"].split()
            ko = datetime.strptime("2026-" + dd + " " + tt, "%Y-%m-%d %H:%M").replace(tzinfo=BJT)
        except Exception:
            continue
        out.append({"id": r["id"], "league": r["league"], "kickoff": r["kickoff"],
                    "home": r["home"], "away": r["away"], "ko": ko})
    return out

def load_state():
    if os.path.exists(STATE):
        try: return json.load(io.open(STATE, encoding="utf-8"))
        except Exception: pass
    return {"pulled": {}}

def save_state(st):
    io.open(STATE, "w", encoding="utf-8").write(json.dumps(st, ensure_ascii=False, indent=1))

def pull_match(t, force=False):
    eid = t["id"]
    now = datetime.now(BJT)
    mins = (t["ko"] - now).total_seconds() / 60.0
    if mins < 0:
        return "skip_finished"
    if not force and not (WINDOW_MIN <= mins <= WINDOW_MAX):
        return "skip_window(%.0fm)" % mins
    od = bsd_get("/events/%d/odds/" % eid)
    pr = bsd_get("/events/%d/prediction/" % eid)
    if "__err__" in od and "__err__" in pr:
        return "fetch_fail"
    ts = datetime.now(BJT).strftime("%Y%m%d_%H%M")
    fn = os.path.join(OUTDIR, "prematch_snap_%d_%s.json" % (eid, ts))
    os.makedirs(OUTDIR, exist_ok=True)
    snap = {
        "id": eid, "league": t["league"], "kickoff": t["kickoff"], "home": t["home"], "away": t["away"],
        "pulled_at": datetime.now(BJT).isoformat(), "mins_to_ko": round(mins, 1),
        "bsd_odds": od.get("odds") if "__err__" not in od else None,
        "bsd_odds_ts": od.get("last_update_at") if "__err__" not in od else None,
        "bsd_pred": pr.get("markets") if "__err__" not in pr else None,
    }
    snap["vs_first"] = calc_vs_first(snap)
    io.open(fn, "w", encoding="utf-8").write(json.dumps(snap, ensure_ascii=False, indent=1))
    return "ok->%s" % os.path.basename(fn)



def _earliest_snap(eid):
    if not os.path.isdir(OUTDIR):
        return None
    fs = sorted(f for f in os.listdir(OUTDIR)
                if f.startswith("prematch_snap_%d_" % eid) and f.endswith(".json"))
    return fs[0] if fs else None

def calc_vs_first(snap):
    """对比该场最早快照, 输出盘口水位变化信号 (临场盘自动比对)."""
    eid = snap.get("id")
    first_fn = _earliest_snap(eid)
    if not first_fn:
        return {"note": "无更早快照, 无法对比"}
    try:
        first = json.load(io.open(os.path.join(OUTDIR, first_fn), encoding="utf-8"))
    except Exception:
        return {"note": "早盘读取失败"}
    o0 = first.get("bsd_odds") or {}
    o1 = snap.get("bsd_odds") or {}
    keys = ["home_win", "draw", "away_win", "over_25_goals", "under_25_goals",
            "over_35_goals", "under_35_goals", "btts_yes"]
    chg = {}
    for k in keys:
        a, b = o0.get(k), o1.get(k)
        if a and b:
            chg[k] = {"first": round(a, 2), "now": round(b, 2), "pct": round((b - a) / a * 100, 1)}
    sig = []
    hw = chg.get("home_win")
    if hw:
        if hw["pct"] <= -3: sig.append("主胜降水≥3%: 资金流入主胜, 方向可信")
        elif hw["pct"] >= 3: sig.append("主胜升水: 资金流出主胜, 谨慎")
    aw = chg.get("away_win")
    if aw and aw["pct"] >= 3: sig.append("客胜升水: 客胜被看衰")
    ov = chg.get("over_25_goals")
    if ov and ov["pct"] <= -2: sig.append("大2.5降水: 大球资金流入")
    if not sig: sig.append("盘口无明显异动")
    return {"vs_snap": first_fn, "changes": chg, "signals": sig}


def main():
    if os.path.exists(os.path.join(ROOT, "analysis_records", "pull_pause.flag")):
        log("拉取已暂停 (检测到 pull_pause.flag, 删除该文件恢复)")
        return

    force_id = None
    if "--id" in sys.argv:
        force_id = int(sys.argv[sys.argv.index("--id") + 1])
    targets = load_targets()
    st = load_state()
    pulled_now = []
    for t in targets:
        key = str(t["id"])
        if force_id is not None and t["id"] != force_id:
            continue
        if not force_id and st["pulled"].get(key):
            continue
        res = pull_match(t, force=force_id is not None)
        if res.startswith("ok"):
            st["pulled"][key] = datetime.now(BJT).isoformat()
            pulled_now.append((t["kickoff"], t["league"], t["home"], t["away"], res))
        elif force_id is not None:
            log("强制拉取 %s %s vs %s: %s" % (t["kickoff"], t["home"], t["away"], res))
        elif res == "fetch_fail":
            log("拉取失败待重试 %s %s vs %s (%.0fm)" % (t["kickoff"], t["home"], t["away"], mins_to(t)))
    save_state(st)
    if pulled_now:
        for p in pulled_now:
            log("赛前拉取 %s %s | %s vs %s | %s" % p)
        log("本轮拉取 %d 场" % len(pulled_now))
    else:
        log("本轮无到窗口场次 (已拉 %d/46)" % len(st["pulled"]))

def mins_to(t):
    return (t["ko"] - datetime.now(BJT)).total_seconds() / 60.0

if __name__ == "__main__":
    main()
