# -*- coding: utf-8 -*-
"""08-22 凌晨 27 场 v2: 注入 match_package 伤停/阵型/BSD盘口情报后完整重算
修复: 上一版 _load_match_info_map 只读 8/16 旧 matches_info, 27 场情报匹配不到 -> 全部"纯数据无伤病情报"
本版: 从 match_package/{eid}.json 构造 info -> 喂给 _injury_pos_check/_formation_check/_bsd_cross_check
输出: rerun_0822_intel.json + rerun_0822_intel.md
"""
import sys, os, io, json, glob, collections
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
from src.live_odds import flatten_events

def norm_team(s):
    import unicodedata, re
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())

# ---- 1. 索引 ----
rows = json.load(io.open(os.path.join(OUT, "odds_compare_0822_rows.json"), encoding="utf-8"))
new_all = json.load(io.open(os.path.join(OUT, "odds_live_0822_matched_final.json"), encoding="utf-8"))
new = new_all["matches"]; PULLED = new_all.get("pulled_at", "")

def ko_to_iso(ko):
    try:
        dd, tt = ko.split()
        return datetime.strptime("2026-" + dd + " " + tt, "%Y-%m-%d %H:%M").replace(tzinfo=BJT).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    except Exception:
        return ""

# ---- 2. 构造快照 CSV（同上一版） ----
import csv, re, unicodedata
def uniq(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())

hdr = ["snapshot_ts","event_id","league","commence_time","home_team","away_team",
       "bookmaker","market","outcome","side","side_key","point","price","last_update"]
crows = []
for r in rows:
    eid = str(r["eid"]); ev = new.get(eid)
    if not ev: continue
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
                    val = str(v.get("value"))
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
                    elif bnm.lower() in ("goals over/under", "over/under", "total goals over/under"):
                        mm = re.match(r"^\s*(Over|Under)\s+(\d+(?:\.\d+)?)\s*$", val, re.I)
                        if not mm: continue
                        side = "over" if mm.group(1).lower()=="over" else "under"
                        line = mm.group(2)
                        crows.append([ts, eid, league, ct, h, a, bname, "totals", val, side, "%s@%s" % (side, line), line, price, ts])
    else:
        # 复用生产 flatten_events (含 classify_side 强匹配 + 市场级补全), 杜绝本地侧边判定偏差
        for fr in flatten_events([ev], league, ts):
            pt = fr.get("point")
            pt_s = "" if pt is None else (("%g" % pt) if pt == int(pt) else ("%.2f" % pt))
            crows.append([fr["snapshot_ts"], eid, league, ct, h, a, fr["bookmaker"], fr["market"],
                          fr["outcome"], fr["side"], fr["side_key"], pt_s, fr["price"], fr["last_update"]])

csv_path = os.path.join(OUT, "snapshots_live_0822.csv")
with io.open(csv_path, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f); w.writerow(hdr); w.writerows(crows)

# ---- 3. 从 match_package 构造情报 info_map ----
def build_pkg_info_map():
    """{(league, home, away): info}, info 兼容 matches_info 格式"""
    out = {}
    for fp in glob.glob(os.path.join(ROOT, "analysis_records", "match_package", "*.json")):
        try:
            d = json.load(io.open(fp, encoding="utf-8"))
        except Exception:
            continue
        info = {}
        inj = d.get("injuries") or {}
        # 只要 BSD 已拉取伤停(字段存在), 即使为空也标记已查 -> 避免误标"纯数据无伤病情报"
        if isinstance(inj, dict) and ("home" in inj or "away" in inj or "home_covered" in inj or "away_covered" in inj):
            info["injuries"] = inj
        lu = d.get("lineups") or {}
        if lu.get("formation") or lu.get("confidence"):
            info["bsd_lineups"] = {
                "status": lu.get("lineup_status"),
                "home_conf": (lu.get("confidence") or {}).get("home"),
                "away_conf": (lu.get("confidence") or {}).get("away"),
                "formation": lu.get("formation") or {},
                "coach": (d.get("schedule") or {}).get("preferred_formation") or {},
            }
        od = d.get("odds") or {}
        if od.get("consensus"):
            info["bsd_odds"] = {"consensus": od.get("consensus")}
        sch = d.get("schedule") or {}
        if sch.get("coaches"):
            info["bsd_prediction"] = {
                "expected_goals": {},
                "recommendations": {},
                "confidence": None,
                "coaches": sch.get("coaches"),
            }
            info["coaches"] = sch.get("coaches")
        if not info:
            continue
        key = (d.get("league"), d.get("home"), d.get("away"))
        out[key] = info
    return out

pkg_info = build_pkg_info_map()
print("match_package info 匹配池:", len(pkg_info))

# ---- 4. 重算 ----
team_stats, lavg, index = SU.load_team_stats()
events, future_skipped = SU.parse_snapshots(path=csv_path)
old_info = SU._load_match_info_map()
coach_cache = None
try:
    import coach_quant as cq
    coach_cache = cq.load_cache()
except Exception:
    pass

results = []
used_pkg = 0
for m in events:
    _info = old_info.get((m["league"], m["home"], m["away"]))
    # 优先 match_package 情报（含本轮 27 场）
    pk = pkg_info.get((m["league"], m["home"], m["away"]))
    if pk is None:
        # 按队名模糊匹配
        _nh, _na = norm_team(m["home"]), norm_team(m["away"])
        for (lg, h, a), inf in pkg_info.items():
            if norm_team(h) == _nh and norm_team(a) == _na:
                pk = inf; break
    if pk:
        if _info is None:
            _info = {}
        _info = dict(_info); _info.update(pk)
        used_pkg += 1
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
            # BSD伤停已查(即使为空) -> 移除"纯数据无伤病情报", 改为 BSD伤停情报 + 覆盖状态
            # 语义: match_package 存在 = 已拉取 BSD 伤停; 空表示 BSD 无伤停(或未确认), 不再误标"纯数据无伤病情报"
            inj = _info.get("injuries") or {}
            has_inj_fields = "home" in inj or "away" in inj or "home_covered" in inj or "away_covered" in inj
            if has_inj_fields and "纯数据无伤病情报" in (r.get("risk_tags") or []):
                r["risk_tags"].remove("纯数据无伤病情报")
                r["risk_tags"].insert(0, "BSD伤停情报[主%d客%d]" % (len(inj.get("home") or []), len(inj.get("away") or [])))
            if inj.get("home_covered") is False or inj.get("away_covered") is False:
                tag = "伤停覆盖不全"
                if tag not in r.setdefault("risk_tags", []):
                    r["risk_tags"].append(tag)
        except Exception:
            pass
    results.append({"id": m.get("id"), "league": m["league"], "home": m["home"], "away": m["away"],
                    "ct": m["ct"].astimezone(BJT).strftime("%m-%d %H:%M"), "snap": m.get("snap"),
                    "books": m.get("books_used"), "result": r})

json.dump({"pulled_at": PULLED, "n": len(results), "used_pkg": used_pkg, "matches": results},
          io.open(os.path.join(OUT, "rerun_0822_intel.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

for x in results:
    r = x["result"]
    bb = r.get("best_bet") or {}
    bb_s = ("%s %.0f%% @%.2f EV%+.1f%% ★%d[%s]" % (bb["name"], bb["prob"]*100, bb["odds"], bb["ev"]*100, bb.get("star",0), bb.get("ev_tier","?"))) if bb else "-无正EV-"
    di = r.get("direction") or {}
    dir_s = ("%s %.0f%%@%.2f EV%+.1f%%" % (di["name"], di["prob"]*100, di["odds"], di["ev"]*100)) if di.get("name") else "-无盘口-"
    if di.get("vetoed"): dir_s += " ⛔否决"
    risk_s = (" 风险:%s" % ",".join(r.get("risk_tags") or [])) if r.get("risk_tags") else ""
    fm = r.get("formation") or {}
    form_s = (" 阵型[%s/%s]" % (fm.get("home") or "-", fm.get("away") or "-")) if (fm.get("home") or fm.get("away")) else ""
    bsd_s = ""
    if r.get("bsd") and r["bsd"].get("ev") is not None:
        bsd_s = " BSD-EV%+.1f%%" % (r["bsd"]["ev"]*100)
    lam = r.get("lambda") or {}
    print("%s %-14s %s vs %s | λ%.2f/%.2f | 方向[%s] | BEST[%s]%s%s%s" % (
        x["ct"], x["league"], x["home"], x["away"], lam.get("home",0), lam.get("away",0), dir_s, bb_s, risk_s, form_s, bsd_s))
n_bb = sum(1 for x in results if x["result"].get("best_bet"))
n_pos = sum(1 for x in results if any(b.get("ev",0)>0 for b in (x["result"].get("bets") or [])))
n_veto = sum(1 for x in results if x["result"].get("direction",{}).get("vetoed"))
print("\n出单:%d/%d  正EV:%d/%d  硬否决:%d  情报注入:%d/%d" % (n_bb, len(results), n_pos, len(results), n_veto, used_pkg, len(results)))
print("saved:", os.path.join(OUT, "rerun_0822_intel.json"))
