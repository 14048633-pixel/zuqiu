# -*- coding: utf-8 -*-
"""只拉 BEST 场次临场盘: BSD 现场拉最新 consensus -> 重算 BEST 腿 EV
输出: 每场 原EV(扫描时) vs 临场EV vs ΔEV -> 出单保持/掉出/新增"""
import sys, os, io, json, glob, unicodedata, re
from datetime import datetime, timezone, timedelta

ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, ROOT)
import scan_upcoming as su
import bsd_extra

BJT = timezone(timedelta(hours=8))

def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def latest_scan():
    fs = sorted(glob.glob(os.path.join(ROOT, "analysis_records", "scan_next24h_*.json")), key=os.path.getmtime)
    d = json.load(io.open(fs[-1], encoding="utf-8"))
    return [m for m in d if m.get("best_bet")], os.path.basename(fs[-1])

def match_pkg(m):
    best = None; best_score = -1
    for fp in glob.glob(os.path.join(ROOT, "analysis_records", "match_package", "*.json")):
        try:
            d = json.load(io.open(fp, encoding="utf-8"))
        except Exception:
            continue
        sc = 0
        if m.get("id") and str(m["id"]) in (str(d.get("id")), str(d.get("id")).replace("apifb", "")):
            sc = 100
        else:
            nh, na = _norm(m["home"]), _norm(m["away"])
            dh, da = _norm(d.get("home")), _norm(d.get("away"))
            if nh == dh and na == da: sc = 80
            elif (nh in dh or dh in nh) and (na in da or da in na): sc = 50
            elif nh == dh or na == da: sc = 20
        if sc > best_score:
            best_score = sc; best = d
    return best if best_score >= 50 else None

OU_MAP = {"大2.50": ("over_25_goals", "under_25_goals", False), "小2.50": ("over_25_goals", "under_25_goals", False),
          "大3.00": ("over_35_goals", "under_35_goals", True), "小3.00": ("over_35_goals", "under_35_goals", True)}
X2_MAP = {"1X2主胜": "home_win", "1X2平局": "draw", "1X2客胜": "away_win"}

def live_ev(name, prob, cons):
    if name in OU_MAP:
        ov, un, approx = OU_MAP[name]
        p = cons.get(ov) or cons.get(un)
        return (p, approx) if p else (None, approx)
    if name in X2_MAP:
        return (cons.get(X2_MAP[name]), False)
    return (None, False)  # 让球: BSD 无亚盘

def main():
    bests, scan_name = latest_scan()
    print("最新扫描:", scan_name, "| BEST 场次:", len(bests))
    out = []
    for m in bests:
        bb = m["best_bet"]
        pkg = match_pkg(m)
        row = {"ko": m["ko_bjt"], "league": m["league"], "home": m["home"], "away": m["away"],
               "leg": bb["name"], "orig_prob": bb["prob"], "orig_odds": bb["odds"], "orig_ev": bb["ev"],
               "star": bb["star"], "live_ev": None, "delta_ev": None, "status": "无BSD包",
               "cons_src": None, "pulled_at": None}
        if pkg:
            eid = pkg.get("id")
            cons = None; src = "package"
            try:
                od = bsd_extra.fetch_odds(eid) if eid is not None else None
                if od and od.get("consensus"):
                    cons = od["consensus"]; src = "live_fetch"
                    row["pulled_at"] = datetime.now(BJT).isoformat(timespec="seconds")
            except Exception:
                cons = None
            if cons is None:
                cons = (pkg.get("odds") or {}).get("consensus") or {}
                src = "package(旧)"
                row["pulled_at"] = pkg.get("pulled_at")
            row["cons_src"] = src
            new_price, approx = live_ev(bb["name"], bb["prob"], cons)
            if new_price:
                n_ev = bb["prob"] * new_price - 1
                row["live_odds"] = new_price
                row["approx_ou"] = approx
                row["live_ev"] = round(n_ev, 4)
                row["delta_ev"] = round(n_ev - bb["ev"], 4)
                row["status"] = ("临场确认(近似3.5线)" if approx and n_ev >= 0.05
                                 else "临场掉出" if n_ev < 0.05 else "临场确认")
            else:
                row["status"] = "BSD无此市场(让球/缺盘)"
        out.append(row)
    # 输出
    ts = datetime.now(BJT).strftime("%Y%m%d_%H%M")
    jp = os.path.join(ROOT, "analysis_records", "best_live_confirm_%s.json" % ts)
    json.dump(out, io.open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("saved", jp)
    print()
    print("%-6s %-9s %-26s %-8s %8s %8s %8s  %s" % ("时间", "联赛", "对阵", "腿", "原EV", "临场EV", "ΔEV", "状态"))
    for r in out:
        ev = ("%+.1f%%" % (r["orig_ev"] * 100)) if r["orig_ev"] is not None else "-"
        lv = ("%+.1f%%" % (r["live_ev"] * 100)) if r["live_ev"] is not None else "-"
        dv = ("%+.1f%%" % (r["delta_ev"] * 100)) if r["delta_ev"] is not None else "-"
        print("%-6s %-9s %-26s %-8s %8s %8s %8s  %s(%s)" % (r["ko"], r["league"], r["home"] + " vs " + r["away"], r["leg"], ev, lv, dv, r["status"], r["cons_src"]))

if __name__ == "__main__":
    main()
