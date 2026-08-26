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

H2H = {"home": 2.0, "away": 3.4, "draw": 3.6}

# r2 概率禁带: Beijing FC vs Henan FC, hdp=-1.0 (原测试盘口)
m = _mk("Beijing FC", "Henan FC", "中超", H2H,
        {"hdp_home": -1.0, "home_price": 1.95, "away_price": 1.90},
        {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
r = su.analyze_match(m, ts, lavg, index)
print("== r2北京-1.0: best=%s" % ((r.get("best_bet") or {}).get("name")))
for b in r["bets"]:
    print("   %-12s prob=%.4f raw=%s ev=%+.4f" % (b["name"], b["prob"], b.get("prob_raw"), b["ev"]))
print("   notes含禁带:", any("概率禁带" in n for n in r.get("notes",[])))
print("   notes:", [n for n in r.get("notes",[]) if "禁" in n or "概率" in n])

# r1b2 阈值0.03
m1b = _mk("Casa Pia", "Benfica", "葡超", {"home": 16.5, "draw": 7.2, "away": 1.24},
          {"hdp_home": 1.5, "home_price": 2.14, "away_price": 1.68},
          {"line": 2.5, "over_price": 1.6, "under_price": 2.3})
_o = su.SMALL_250_HIGH_EV; su.SMALL_250_HIGH_EV = 0.03
r1b2 = su.analyze_match(m1b, ts, lavg, index)
su.SMALL_250_HIGH_EV = _o
x = [b for b in r1b2["bets"] if b["name"] == "小2.50"]
print("== r1b2 阈值0.03: 小2.50在bets:", bool(x), "| EV:", x[0]["ev"] if x else None, "| best:", (r1b2.get("best_bet") or {}).get("name"))
print("   notes:", [n for n in r1b2.get("notes",[]) if "规则6" in n or "禁" in n])

# ⑧A m6 line3.5 stake_factor
m6 = _mk("Shanghai Shenhua FC", "Henan FC", "中超",
         {"home": 2.0, "away": 3.4, "draw": 3.6},
         {"hdp_home": -0.5, "home_price": 2.05, "away_price": 2.05},
         {"line": 3.5, "over_price": 1.95, "under_price": 1.95})
r6 = su.analyze_match(m6, ts, lavg, index)
bb = r6.get("best_bet") or {}
print("== ⑧A line3.5: best=%s star=%s stake=%s" % (bb.get("name"), r6.get("star"), bb.get("stake_factor")))
print("   note含规则8:", any("规则8赔率高估区" in n for n in r6.get("notes",[])))
print("   tags:", [t for t in r6.get("risk_tags",[]) if "高估" in t or "降权" in t])

# m5 预警 1.95/1.95 tags
H2H_DW = {"home": 2.5, "draw": 3.4, "away": 3.0}
m5 = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H_DW, None,
         {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
r5 = su.analyze_match(m5, ts, lavg, index)
print("== 预警1.95/1.95: best=%s star=%s" % ((r5.get("best_bet") or {}).get("name"), r5.get("star")))
print("   tags:", r5.get("risk_tags"))

su.recent_league_avg = _orig_avg
for _k, _v in _oua_save.items():
    su.CAL[_k]["ou_strength_adj"] = _v
