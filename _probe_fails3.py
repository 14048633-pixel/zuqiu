# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\足球分析\prediction_v2")
import scan_upcoming as su
from datetime import datetime, timezone

ts, lavg, index = su.load_team_stats()
_orig_avg = su.recent_league_avg
su.recent_league_avg = lambda: {"J1": (3.35, 20), "中超": (3.04, 30), "英超": (2.8719, 30)}
_oua_save = {_k: _v.get("ou_strength_adj") for _k, _v in su.CAL.items()}
for _c in su.CAL.values():
    _c["ou_strength_adj"] = {}

def _mk(home, away, league, h2h, sp, tt):
    return {"id": "t", "league": league, "home": home, "away": away,
            "ct": datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc),
            "snap": "2026-08-16T10:00:00Z", "h2h": h2h, "spread": sp, "totals": tt}

def legs(r):
    return {b["name"]: (b["prob"], b.get("prob_raw"), round(b["ev"],4)) for b in r["bets"]}

H2H = {"home": 2.0, "away": 3.4, "draw": 3.6}

# A) r3 中浅让: totals line 3.5
m = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H,
        {"hdp_home": -0.5, "home_price": 1.95, "away_price": 1.95},
        {"line": 3.5, "over_price": 1.95, "under_price": 1.95})
r = su.analyze_match(m, ts, lavg, index)
print("A) 中浅让 line3.5: best=%s star=%s" % ((r.get("best_bet") or {}).get("name"), r.get("star")))
print("   ", legs(r))

# B) ⑧A m6: totals line 3.5
m = _mk("Shanghai Shenhua FC", "Henan FC", "中超",
        {"home": 2.0, "away": 3.4, "draw": 3.6},
        {"hdp_home": -0.5, "home_price": 2.05, "away_price": 2.05},
        {"line": 3.5, "over_price": 1.95, "under_price": 1.95})
r = su.analyze_match(m, ts, lavg, index)
print("B) ⑧A line3.5: best=%s star=%s tags=%s" % ((r.get("best_bet") or {}).get("name"), r.get("star"), [t for t in r.get("risk_tags",[]) if "高估" in t]))
print("   ", legs(r))

# C) m5 预警: totals 1.95/1.95
H2H_DW = {"home": 2.5, "draw": 3.4, "away": 3.0}
m = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H_DW, None,
        {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
r = su.analyze_match(m, ts, lavg, index)
print("C) 预警 line2.5 1.95/1.95: best=%s star=%s" % ((r.get("best_bet") or {}).get("name"), r.get("star")))
print("   ", legs(r))

# D) r2 概率禁带: 找让球主 raw in [0.65,0.70)
pairs = [("Shanghai Shenhua FC", "Qingdao West Coast"), ("Chengdu Rongcheng FC", "Qingdao West Coast"),
         ("Shanghai Port", "Henan FC"), ("Beijing FC", "Henan FC"), ("Chengdu Rongcheng FC", "Dalian Yingbo")]
for h, a in pairs:
    for hdp in [-0.5, -0.8]:
        m = _mk(h, a, "中超", H2H,
                {"hdp_home": hdp, "home_price": 1.95, "away_price": 1.90},
                {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
        r = su.analyze_match(m, ts, lavg, index)
        gz = [b for b in r["bets"] if b["name"].startswith("让球主")]
        if gz:
            raw = gz[0].get("prob_raw") or gz[0]["prob"]
            ban = "概率禁带" in " ".join(r.get("notes", []))
            print("D) %s %s hdp=%s: 让主raw=%.4f 禁带=%s best=%s" % (h[:16], a[:16], hdp, raw, ban, (r.get("best_bet") or {}).get("name")))

su.recent_league_avg = _orig_avg
for _k, _v in _oua_save.items():
    su.CAL[_k]["ou_strength_adj"] = _v
