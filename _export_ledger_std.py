# -*- coding: utf-8 -*-
"""14场全方向对账 -> 标准 bet_ledger 列格式 CSV (独立文件, 不合并生产账本)
标准列: date,league,match,home,away,bet_name,prob,odds,ev,star,ev_tier,stake_factor,
        result,ret,pnl,status,src,veto,risk_tags,divergence_pp,placed_odds,bookmaker,verified,
        kickoff,data_src,snap_age_h,upset_level,data_note,scan_ts,coach_atk_mod,coach_def_mod,coach_sample_size
"""
import sys, os, json, io, csv, glob
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
BJT = timezone(timedelta(hours=8))
COLS = ["date","league","match","home","away","bet_name","prob","odds","ev","star","ev_tier",
        "stake_factor","result","ret","pnl","status","src","veto","risk_tags","divergence_pp",
        "placed_odds","bookmaker","verified","kickoff","data_src","snap_age_h","upset_level",
        "data_note","scan_ts","coach_atk_mod","coach_def_mod","coach_sample_size"]

def latest(prefix):
    xs = [x for x in os.listdir(os.path.join(ROOT, "analysis_records"))
          if x.startswith(prefix) and x.endswith(".json")]
    return sorted(xs)[-1]

def main():
    full_f = latest("scan24h_settle_full_")
    ana_f = latest("scan24h_analysis_")
    full = json.load(io.open(os.path.join(ROOT, "analysis_records", full_f), encoding="utf-8"))
    ana = json.load(io.open(os.path.join(ROOT, "analysis_records", ana_f), encoding="utf-8"))
    a_idx = {(m["ct"], m["home"], m["away"]): m for m in ana["matches"]}
    out = []
    for r in full["rows"]:
        am = a_idx.get((r["ct"], r["home"], r["away"]), {})
        try:
            kt = datetime.strptime(r["ct"], "%m-%d %H:%M").replace(year=2026, tzinfo=BJT).isoformat()
        except Exception:
            kt = ""
        date = r["ct"][:5].replace("-", "/") + "/2026" if len(r["ct"]) >= 5 else ""
        base = {
            "date": date, "league": r["league"], "match": "%s vs %s" % (r["home"], r["away"]),
            "home": r["home"], "away": r["away"],
            "stake_factor": "", "status": "已结算", "src": "scan24h对账",
            "veto": 1 if r["vetoed"] else 0,
            "risk_tags": ";".join(r.get("risk", [])),
            "kickoff": kt, "data_src": "", "snap_age_h": am.get("snap_age_h"),
            "scan_ts": full["ts"],
        }
        for l in r["legs"]:
            res = l["result"]
            odds = l.get("odds") or 1.0
            if res == "win":
                ret, pnl = odds, odds - 1.0
            elif res == "lose":
                ret, pnl = 0.0, -1.0
            elif res == "push":
                ret, pnl = 1.0, 0.0
            elif res == "half":
                ret, pnl = (1.0 + odds) / 2.0, (odds - 1.0) / 2.0
            else:
                ret, pnl = "", ""
            row = dict(base)
            row.update({
                "bet_name": l["name"], "prob": l.get("prob"), "odds": odds,
                "ev": l.get("ev"), "star": l.get("star") or "",
                "ev_tier": l.get("ev_tier") or "",
                "result": "win" if res == "win" else ("lose" if res == "lose" else ("push" if res == "push" else ("half" if res == "half" else res or ""))),
                "ret": ret, "pnl": pnl,
            })
            out.append({c: row.get(c, "") for c in COLS})
    outp = os.path.join(ROOT, "analysis_records", "bet_ledger_scan24h_20260822.csv")
    with open(outp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(out)
    # 标准统计
    def st(rows):
        n = len(rows)
        if not n: return None
        wins = sum(1 for x in rows if x["result"] == "win")
        half = sum(1 for x in rows if x["result"] == "half")
        pushes = sum(1 for x in rows if x["result"] == "push")
        roi = sum((float(x["pnl"]) if x["pnl"] != "" else 0.0) for x in rows) / n
        rate = (wins + 0.5 * half) / (n - pushes) if (n - pushes) else None
        return {"n": n, "wins": wins, "half": half, "pushes": pushes,
                "rate": ("%.1f%%" % (100 * rate)) if rate is not None else "—",
                "roi_flat": ("%+.1f%%" % (100 * roi))}
    all_l = out
    pos = [x for x in all_l if (x["ev"] not in ("", None)) and x["ev"] > 0]
    main_dir = []
    for r in full["rows"]:
        if r["direction_name"]:
            main_dir.append([x for x in all_l if x["match"] == "%s vs %s" % (r["home"], r["away"])
                             and x["bet_name"] == r["direction_name"]][0])
    print("saved:", outp, "| 行数:", len(out))
    print()
    print("== 标准统计（每注1本金, 平注口径） ==")
    for nm, rows in [("全方向(1X2+让球+大小, 含对冲侧)", all_l),
                     ("正EV方向(模型建议)", pos),
                     ("主方向(每场1个)", main_dir)]:
        s = st(rows)
        if s:
            print("%s: %d注 | 命中%d 半赢%d 走水%d | 命中率%s | 平注ROI %s" % (
                nm, s["n"], s["wins"], s["half"], s["pushes"], s["rate"], s["roi_flat"]))
    # 按市场
    print()
    for tag, nm in [("1X2", "1X2"), ("让球", "让球"), ("大", "大小球")]:
        rows = [x for x in all_l if x["bet_name"].startswith(tag)]
        s = st(rows)
        if s:
            print("%s: %d注 | 命中率%s | 平注ROI %s" % (nm, s["n"], s["rate"], s["roi_flat"]))

if __name__ == "__main__":
    main()
