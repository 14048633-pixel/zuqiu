# -*- coding: utf-8 -*-
import sys, os, io, json, glob, unicodedata, re
from datetime import datetime, timezone, timedelta

ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, ROOT)
import scan_upcoming as su
import bsd_extra

BJT = timezone(timedelta(hours=8))
NOW = datetime.now(timezone.utc)

def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def load_baseline():
    fs = sorted(glob.glob(os.path.join(ROOT, "analysis_records", "scan_next24h_*.json")), key=os.path.getmtime)
    d = json.load(io.open(fs[-1], encoding="utf-8"))
    base = {}
    for m in d:
        base[(_norm(m.get("home")), _norm(m.get("away")))] = m
    return base, os.path.basename(fs[-1])

def main():
    su.recent_league_avg = lambda: {}
    lst = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan24h_20260826_0000.json"), encoding="utf-8"))["matches"]
    team_stats, lavg, index = su.load_team_stats()
    base, scan_name = load_baseline()

    # 英联杯场次(从 scan24h 原始列表选)
    targets = []
    for x in lst:
        try:
            ct = datetime.fromisoformat(x["ct"].replace("Z", "+00:00"))
        except Exception:
            continue
        if ct <= NOW:
            continue  # 已开场跳过
        targets.append(x)
    # 只保留英联杯 (用事件 detail league 判断不可靠, 直接用映射键近似: scan24h 里 league 字段)
    cb = [x for x in targets if (x.get("league") or "").lower() in ("carabao cup", "carabao", "英联杯")]
    if not cb:
        # 兜底: 用 BSD 包 league_name
        cb = []
        for x in targets:
            fp = os.path.join(ROOT, "analysis_records", "match_package", "%d.json" % x["id"])
            try:
                lg = json.load(io.open(fp, encoding="utf-8")).get("league") or ""
            except Exception:
                lg = ""
            if "carabao" in lg.lower():
                cb.append(x)
    print("英联杯未开场场次:", len(cb))
    out = []
    for x in cb:
        pid = x["id"]
        ct = datetime.fromisoformat(x["ct"].replace("Z", "+00:00"))
        row = {"bsd_id": pid, "ko_bjt": ct.astimezone(BJT).strftime("%m-%d %H:%M"),
               "home": x["home"], "away": x["away"]}
        cons = None; src = None
        try:
            od = bsd_extra.fetch_odds(int(pid))
            if od and od.get("consensus"):
                cons = od["consensus"]; src = "BSD临场"
        except Exception as e:
            print("fetch_odds err", pid, repr(e)[:120]); cons = None
        if not cons:
            # 用包内旧 consensus
            fp = os.path.join(ROOT, "analysis_records", "match_package", "%d.json" % pid)
            try:
                pkg = json.load(io.open(fp, encoding="utf-8"))
                cons = (pkg.get("odds") or {}).get("consensus") or {}
                src = "包内旧盘(%s)" % (pkg.get("pulled_at") or "?")
            except Exception:
                cons = {}
                src = "无盘"
        ev = {"id": pid, "league": "英联杯", "home": x["home"], "away": x["away"],
              "ct": ct, "snap": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
              "odds": __import__("collections").defaultdict(list)}
        if cons.get("home_win") and cons.get("draw") and cons.get("away_win"):
            ev["h2h"] = {"home": cons["home_win"], "draw": cons["draw"], "away": cons["away_win"]}
        if cons.get("over_25_goals") and cons.get("under_25_goals"):
            ev["totals"] = {"line": 2.5, "over_price": cons["over_25_goals"], "under_price": cons["under_25_goals"]}
        try:
            r = su.analyze_match(ev, team_stats, lavg, index)
        except Exception as e:
            row["error"] = repr(e)[:200]
            out.append(row); continue
        di = r.get("direction") or {}
        bb = r.get("best_bet")
        bk = (_norm(x["home"]), _norm(x["away"]))
        b = base.get(bk)
        row.update({
            "cons_src": src, "pulled_at": NOW.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "lambda": r.get("lambda"), "direction": di.get("name"), "dir_prob": di.get("prob"),
            "dir_odds": di.get("odds"), "dir_ev": di.get("ev"),
            "vetoed": di.get("vetoed"), "veto_reason": di.get("veto_reason"),
            "draw_warn": r.get("draw_warn"), "star": r.get("star"), "risk_tags": r.get("risk_tags") or [],
            "best_bet": bb, "notes": r.get("notes") or [],
            # 基线对比
            "base_direction": (b or {}).get("direction"), "base_dir_ev": (b or {}).get("dir_ev"),
            "base_star": (b or {}).get("star"), "base_veto": (b or {}).get("vetoed"),
            "base_best": (b or {}).get("best_bet"),
        })
        # 状态判定
        st = []
        if row["vetoed"]: st.append("否决")
        elif bb: st.append("BEST")
        else: st.append("参考")
        if (b or {}).get("best_bet") and not bb: st.append("掉出")
        elif not (b or {}).get("best_bet") and bb: st.append("新增")
        elif bb and (b or {}).get("best_bet"):
            n = bb.get("name"); o = (b or {}).get("best_bet") or {}
            if n != o.get("name"): st.append("换腿")
            else:
                de = (bb.get("ev") or 0) - (o.get("ev") or 0)
                st.append("保持(Δ%+.1f%%)" % (de * 100))
        row["status"] = "/".join(st)
        out.append(row)
    out.sort(key=lambda r: r["ko_bjt"])
    ts = NOW.astimezone(BJT).strftime("%Y%m%d_%H%M")
    jp = os.path.join(ROOT, "analysis_records", "carabao_live_%s.json" % ts)
    json.dump(out, io.open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("saved", jp)
    print()
    print("%-6s %-26s %-8s %10s %10s %-5s  %s" % ("时间", "对阵", "方向", "EV", "盘源", "星", "状态"))
    for r in out:
        ev = ("%+.1f%%" % (r["dir_ev"]*100)) if r.get("dir_ev") is not None else "-"
        be = ("%+.1f%%" % (r["base_dir_ev"]*100)) if r.get("base_dir_ev") is not None else "-"
        print("%-6s %-26s %-8s %s→%s %-10s %-5s %s" % (
            r["ko_bjt"], r["home"]+" vs "+r["away"], r.get("direction") or "-", be, ev, r.get("cons_src") or "-", r.get("star"), r.get("status")))
if __name__ == "__main__":
    main()
