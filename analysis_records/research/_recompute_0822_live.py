# -*- coding: utf-8 -*-
"""08-22 凌晨 27 场：用最新赔率(odds_live_0822_matched_final.json)重算完整模型。
流程: 新赔率 -> 临时snapshots CSV -> scan_upcoming.parse_snapshots -> analyze_match
输出: rerun_0822_live.json + rerun_0822_live.md
"""
import sys, os, io, json, csv, re, unicodedata, collections
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, os.path.join(ROOT, "src", "features"))
sys.path.insert(0, os.path.join(ROOT, "src", "models"))
sys.path.insert(0, os.path.join(ROOT, "src", "strategy"))
sys.path.insert(0, os.path.join(ROOT, "src", "rules"))
OUT = os.path.join(ROOT, "analysis_records", "research")
BJT = timezone(timedelta(hours=8))

import scan_upcoming as SU

def uniq(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())

# ---- 1. 读索引与最新赔率 ----
rows = json.load(io.open(os.path.join(OUT, "odds_compare_0822_rows.json"), encoding="utf-8"))
new_all = json.load(io.open(os.path.join(OUT, "odds_live_0822_matched_final.json"), encoding="utf-8"))
new = new_all["matches"]
PULLED = new_all.get("pulled_at", "")

def ko_to_iso(ko):
    try:
        dd, tt = ko.split()
        return datetime.strptime("2026-" + dd + " " + tt, "%Y-%m-%d %H:%M").replace(tzinfo=BJT).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    except Exception:
        return ""

# ---- 2. 构建快照 CSV 行 ----
hdr = ["snapshot_ts","event_id","league","commence_time","home_team","away_team",
       "bookmaker","market","outcome","side","side_key","point","price","last_update"]
crows = []
for r in rows:
    eid = str(r["eid"]); ev = new.get(eid)
    if not ev:
        print("NO ODDS:", eid); continue
    league = r["league"]; h, a = r["home"], r["away"]
    ct = ev.get("commence_time") or ko_to_iso(r["ko"])
    ts = ev.get("pulled_at") or PULLED
    src = ev.get("source")
    if src == "api-football":
        eid = "apifb" + eid
        for bk in ev.get("bookmakers") or []:
            bname = "apifb:" + (bk.get("name") or bk.get("bookmaker") or "?")
            for b in bk.get("bets") or []:
                bnm = b.get("name") or ""
                for v in b.get("values") or []:
                    val = str(v.get("value")); 
                    try: price = float(v.get("odd"))
                    except Exception: continue
                    if bnm.lower() == "match winner":
                        side = {"Home":"home","Draw":"draw","Away":"away"}.get(val)
                        if not side: continue
                        crows.append([ts, eid, league, ct, h, a, bname, "h2h", val, side, side, "", price, ts])
                    elif bnm.lower() == "asian handicap":
                        mm = re.match(r"^\s*(Home|Away)\s+([+-]\d+(?:\.\d+)?)\s*$", val)
                        if not mm: continue
                        side = "home" if mm.group(1).lower()=="home" else "away"
                        line = mm.group(2)
                        crows.append([ts, eid, league, ct, h, a, bname, "asian_handicap", val, side, "%s@%s" % (side, line), line, price, ts])
                    elif "over/under" in bnm.lower():
                        mm = re.match(r"^\s*(Over|Under)\s+(\d+(?:\.\d+)?)\s*$", val, re.I)
                        if not mm: continue
                        side = "over" if mm.group(1).lower()=="over" else "under"
                        line = mm.group(2)
                        crows.append([ts, eid, league, ct, h, a, bname, "totals", val, side, "%s@%s" % (side, line), line, price, ts])
    else:
        for bk in ev.get("bookmakers") or []:
            bkey = bk.get("key") or bk.get("title") or "?"
            bk_ts = bk.get("last_update") or ts
            for mk in bk.get("markets") or []:
                mkey = mk.get("key")
                for oc in mk.get("outcomes") or []:
                    name = str(oc.get("name") or ""); pt = oc.get("point")
                    try: price = float(oc.get("price"))
                    except Exception: continue
                    if mkey == "h2h":
                        nh, na = uniq(h), uniq(a); no = uniq(name)
                        if no == nh: side = "home"
                        elif no == na: side = "away"
                        elif "draw" in name.lower(): side = "draw"
                        else: side = "?"
                        if side == "?": continue
                        crows.append([ts, eid, league, ct, h, a, bkey, "h2h", name, side, side, "", price, bk_ts])
                    elif mkey == "spreads":
                        nh, na = uniq(h), uniq(a); no = uniq(name)
                        side = "home" if no == nh else ("away" if no == na else "?")
                        if side == "?" or pt is None: continue
                        pt_s = ("%g" % pt) if pt == int(pt) else ("%.2f" % pt)
                        crows.append([ts, eid, league, ct, h, a, bkey, "spreads", name, side, "%s@%s" % (side, pt_s), pt_s, price, bk_ts])
                    elif mkey == "totals":
                        low = name.lower()
                        if low.startswith("over"): side = "over"
                        elif low.startswith("under"): side = "under"
                        else: continue
                        if pt is None: continue
                        pt_s = ("%g" % pt) if pt == int(pt) else ("%.2f" % pt)
                        crows.append([ts, eid, league, ct, h, a, bkey, "totals", name, side, "%s@%s" % (side, pt_s), pt_s, price, bk_ts])

csv_path = os.path.join(OUT, "snapshots_live_0822.csv")
with io.open(csv_path, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow(hdr); w.writerows(crows)
print("CSV rows:", len(crows), "->", csv_path)

# ---- 3. 重算模型 ----
team_stats, lavg, index = SU.load_team_stats()
events, future_skipped = SU.parse_snapshots(path=csv_path)
print("events:", len(events), "future_skipped:", future_skipped)
info_map = SU._load_match_info_map()
coach_cache = None
try:
    import coach_quant as cq
    coach_cache = cq.load_cache()
except Exception as e:
    print("coach_quant skip:", e)

results = []
for m in events:
    _info = info_map.get((m["league"], m["home"], m["away"]))
    _cm = {}
    if _info and coach_cache:
        try: _cm = cq.match_mods(coach_cache, _info, m["league"])
        except Exception: _cm = {}
    m["coach_mods"] = _cm
    try:
        r = SU.analyze_match(m, team_stats, lavg, index)
    except Exception as e:
        import traceback; traceback.print_exc()
        r = {"error": repr(e)}
    if _info:
        try:
            r["info"] = _info
            r["coach"] = _cm
            r["bsd"] = SU._bsd_cross_check(r, _info)
            r["formation"] = SU._formation_check(r, _info)
            r["injury_pos"] = SU._injury_pos_check(r, _info)
        except Exception:
            pass
    results.append({"id": m.get("id"), "league": m["league"], "home": m["home"], "away": m["away"],
                    "ct": m["ct"].astimezone(BJT).strftime("%m-%d %H:%M"), "snap": m.get("snap"),
                    "books": m.get("books_used"), "result": r})

json.dump({"pulled_at": PULLED, "n": len(results), "matches": results},
          io.open(os.path.join(OUT, "rerun_0822_live.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- 4. 摘要打印 ----
for x in results:
    r = x["result"]
    bb = r.get("best_bet") or {}
    bb_s = ("%s %.0f%% @%.2f EV%+.1f%% ★%d[%s]" % (bb["name"], bb["prob"]*100, bb["odds"], bb["ev"]*100, bb.get("star",0), bb.get("ev_tier","?"))) if bb else "-无正EV-"
    di = r.get("direction") or {}
    dir_s = ("%s %.0f%%@%.2f EV%+.1f%%" % (di["name"], di["prob"]*100, di["odds"], di["ev"]*100)) if di.get("name") else "-无盘口-"
    if di.get("vetoed"): dir_s += " ⛔否决"
    risk_s = (" 风险:%s" % ",".join(r.get("risk_tags") or [])) if r.get("risk_tags") else ""
    lam = r.get("lambda") or {}
    print("%s %-14s %s vs %s | λ%.2f/%.2f | 方向[%s] | BEST[%s]%s" % (
        x["ct"], x["league"], x["home"], x["away"], lam.get("home",0), lam.get("away",0), dir_s, bb_s, risk_s))
n_bb = sum(1 for x in results if x["result"].get("best_bet"))
n_pos = sum(1 for x in results if any(b.get("ev",0)>0 for b in (x["result"].get("bets") or [])))
print("\n出单:%d/%d  正EV场次:%d/%d" % (n_bb, len(results), n_pos, len(results)))
print("saved:", os.path.join(OUT, "rerun_0822_live.json"))
