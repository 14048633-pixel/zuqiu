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

H2H_DW = {"home": 2.5, "draw": 3.4, "away": 3.0}
H2H = {"home": 2.0, "away": 3.4, "draw": 3.6}

# m5 预警 全量dump
m5 = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H_DW, None,
         {"line": 2.5, "over_price": 2.05, "under_price": 1.78})
r5 = su.analyze_match(m5, ts, lavg, index)
print("== m5 预警规则③ full")
print("   risk_tags:", r5.get("risk_tags"))
print("   notes:", r5.get("notes"))
print("   draw_warn:", r5.get("draw_warn"))
print("   direction:", r5.get("direction"))
print("   best:", r5.get("best_bet"))
print("   veto:", {k: v for k, v in r5.items() if "veto" in k.lower() or "ban" in k.lower() or "reject" in k.lower()})

# r2 概率禁带 变体: 盘口 -0.5 / -0.8, 让球价变化
for hdp in [-0.5, -0.8]:
    for hp in [1.95, 2.10]:
        m = _mk("Shandong Taishan", "Qingdao West Coast", "中超", H2H,
                {"hdp_home": hdp, "home_price": hp, "away_price": 1.90},
                {"line": 2.5, "over_price": 1.95, "under_price": 1.95})
        r = su.analyze_match(m, ts, lavg, index)
        gz = [b for b in r["bets"] if b["name"].startswith("让球主")]
        gj = [b for b in r["bets"] if b["name"].startswith("小")]
        pz = gz[0]["prob"] if gz else None
        pj = gj[0]["prob"] if gj else None
        ban = "概率禁带" in " ".join(r.get("notes", []))
        print("r2变体 hdp=%s hp=%s: 让球主prob=%s 小球prob=%s 概率禁带=%s best=%s" % (hdp, hp, pz, pj, ban, (r.get("best_bet") or {}).get("name")))

# r3 中浅让 变体: home_price 降 / over_price 升
for hp in [1.95, 1.85, 1.80]:
    for op in [1.95, 2.05, 2.15]:
        m = _mk("Shanghai Shenhua FC", "Henan FC", "中超", H2H,
                {"hdp_home": -0.5, "home_price": hp, "away_price": 1.95},
                {"line": 2.5, "over_price": op, "under_price": 1.95})
        r = su.analyze_match(m, ts, lavg, index)
        gz = [b for b in r["bets"] if b["name"].startswith("让球主")]
        dl = [b for b in r["bets"] if b["name"].startswith("大")]
        best = (r.get("best_bet") or {}).get("name")
        gz_ev = gz[0]["ev"] if gz else None
        dl_ev = dl[0]["ev"] if dl else None
        print("r3变体 hp=%s op=%s: 让主ev=%s 大ev=%s best=%s" % (hp, op, gz_ev, dl_ev, best))

su.recent_league_avg = _orig_avg
for _k, _v in _oua_save.items():
    su.CAL[_k]["ou_strength_adj"] = _v
