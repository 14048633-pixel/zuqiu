# -*- coding: utf-8 -*-
"""27 场 旧快照(ah5) vs 新赔率(final) 对比: 1X2/大小球/让球 线位+赔率+EV 变化
规则:
  - 1X2: 最低抽水庄(锐盘)
  - 大小球: 每庄每线配对过滤异常价后取跨庄中位价(线为绝对值)
  - 让球: 线为带符号主让线(主-0.75=主让0.75), 跨庄中位价
    * the-odds-api: 主outcome.line(带符号) 配对 客outcome.line
    * API-Football: "Home X" 与 "Away X"(同号标签) 配对, X 即主让线
"""
import sys, os, json, io, re, statistics
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"D:\足球分析"
OUT = os.path.join(ROOT, "analysis_records", "research")

def uniq(s):
    return re.sub(r"[^a-z0-9 ]", "", (str(s or "")).lower()).strip()

scan = json.load(io.open(os.path.join(ROOT, "analysis_records", "scans", "scan_window_20260821_ah5.json"), encoding="utf-8"))
clean = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan48h_20260821_0048_clean.json"), encoding="utf-8"))
targets = {m["id"]: m for m in clean["matches"] if m["kickoff"].startswith("08-22")}
scan_by_home = {}
for m in scan["matches"]:
    scan_by_home.setdefault(uniq(m.get("home")), []).append(m)

def find_old(t):
    cands = scan_by_home.get(uniq(t["home"])) or []
    for m in cands:
        if uniq(m.get("away")) == uniq(t["away"]):
            return m
    return cands[0] if cands else None

old_map = {}
for eid, t in targets.items():
    m = find_old(t)
    if m is None:
        print("OLD MISS:", eid); continue
    old_map[eid] = {"snap": m.get("snap"), "dir_name": (m.get("dir") or {}).get("name"),
                    "dir_ev": (m.get("dir") or {}).get("ev"), "star": m.get("star"),
                    "veto": (m.get("dir") or {}).get("veto_reason"),
                    "bets": {b["name"]: {"odds": b.get("odds"), "prob": b.get("prob"), "ev": b.get("ev")} for b in (m.get("bets") or [])}}

new_all = json.load(io.open(os.path.join(OUT, "odds_live_0822_matched_final.json"), encoding="utf-8"))
PULLED = new_all.get("pulled_at", "")
new = new_all["matches"]

def orr(prices):
    try:
        return sum(1.0 / max(float(v), 1e-9) for v in prices.values() if v)
    except Exception:
        return None

def med(vals):
    vs = sorted(v for v in vals if v)
    return statistics.median(vs) if vs else None

def best_h2h(ev):
    out = None
    is_afb = ev.get("source") == "api-football"
    h, a = uniq(ev.get("home_team")), uniq(ev.get("away_team"))
    for bk in ev.get("bookmakers") or []:
        prices = {}
        if is_afb:
            for b in bk.get("bets") or []:
                if (b.get("name") or "").lower() != "match winner":
                    continue
                for v in b.get("values") or []:
                    val = str(v.get("value")).lower()
                    try:
                        p = float(v.get("odd"))
                    except Exception:
                        continue
                    if val == "home":
                        prices["home"] = p
                    elif val == "draw":
                        prices["draw"] = p
                    elif val == "away":
                        prices["away"] = p
        else:
            for mk in bk.get("markets") or []:
                if mk.get("key") != "h2h":
                    continue
                for oc in mk.get("outcomes") or []:
                    nm = uniq(oc.get("name"))
                    if nm == h:
                        prices["home"] = oc.get("price")
                    elif nm == a:
                        prices["away"] = oc.get("price")
                    elif "draw" in str(oc.get("name", "")).lower():
                        prices["draw"] = oc.get("price")
        if not all(prices.get(k) for k in ("home", "draw", "away")):
            continue
        o = orr(prices)
        if o is None:
            continue
        if out is None or o < out["orr"]:
            out = {"book": bk.get("key") or bk.get("title") or bk.get("name"), "orr": o, "prices": prices}
    return out

def market_odds(ev, kind):
    """-> {line_key: {"home":{med,n,min,max}, "away":{...}, "orr":.., "disp":..}}
       totals: line_key=绝对线; ah: line_key=带符号主让线"""
    pairs = {}          # line_key -> {book: {side: price}}
    is_afb = ev.get("source") == "api-football"
    h, a = uniq(ev.get("home_team")), uniq(ev.get("away_team"))
    for bk in ev.get("bookmakers") or []:
        bname = bk.get("key") or bk.get("title") or bk.get("name") or "?"
        cands = {}
        if is_afb:
            for b in bk.get("bets") or []:
                nm = b.get("name") or ""
                if kind == "totals" and "over/under" not in nm.lower():
                    continue
                if kind == "ah" and "handicap" not in nm.lower():
                    continue
                lp = {}
                for v in b.get("values") or []:
                    try:
                        p = float(v.get("odd"))
                    except Exception:
                        continue
                    val = str(v.get("value"))
                    if kind == "totals":
                        mm = re.match(r"^\s*(Over|Under)\s+(\d+(?:\.\d+)?)\s*$", val, re.I)
                        if not mm:
                            continue
                        side = "over" if mm.group(1).lower() == "over" else "under"
                        line = abs(float(mm.group(2)))
                    else:
                        mm = re.match(r"^\s*(Home|Away)\s+([+-]\d+(?:\.\d+)?)\s*$", val)
                        if not mm:
                            continue
                        # 同号标签: Home X 与 Away X 是同一盘, X 即主让线
                        side = "home" if mm.group(1).lower() == "home" else "away"
                        line = float(mm.group(2))
                    lp.setdefault(line, {})[side] = p
                for line, pair in lp.items():
                    need = ("over", "under") if kind == "totals" else ("home", "away")
                    if not all(s in pair for s in need):
                        continue
                    o = orr(pair)
                    if o is None:
                        continue
                    cur = cands.get(line)
                    if cur is None or o < cur[0]:
                        cands[line] = (o, dict(pair))
        else:
            for mk in bk.get("markets") or []:
                key = mk.get("key")
                if kind == "totals" and key != "totals":
                    continue
                if kind == "ah" and key != "spreads":
                    continue
                lp = {}
                if kind == "totals":
                    for oc in mk.get("outcomes") or []:
                        low = str(oc.get("name", "")).lower(); pt = oc.get("point")
                        if pt is None:
                            continue
                        try:
                            line = abs(float(pt))
                        except Exception:
                            continue
                        if low.startswith("over"):
                            side = "over"
                        elif low.startswith("under"):
                            side = "under"
                        else:
                            continue
                        lp.setdefault(line, {})[side] = oc.get("price")
                else:
                    # spreads: 主outcome.line=带符号主让线, 客outcome.line=镜像
                    home_pt = away_pt = None
                    hp = ap = None
                    for oc in mk.get("outcomes") or []:
                        nm = uniq(oc.get("name")); pt = oc.get("point")
                        if pt is None:
                            continue
                        if nm == h:
                            home_pt, hp = float(pt), oc.get("price")
                        elif nm == a:
                            away_pt, ap = float(pt), oc.get("price")
                    if home_pt is None or hp is None:
                        continue
                    line = home_pt  # 带符号主让线
                    lp.setdefault(line, {})["home"] = hp
                    if away_pt is not None and ap is not None:
                        lp[line]["away"] = ap
                for line, pair in lp.items():
                    need = ("over", "under") if kind == "totals" else ("home", "away")
                    if not all(s in pair for s in need):
                        continue
                    o = orr(pair)
                    if o is None:
                        continue
                    cur = cands.get(line)
                    if cur is None or o < cur[0]:
                        cands[line] = (o, dict(pair))
        for line, (o, pair) in cands.items():
            pairs.setdefault(line, {})[bname] = pair
    out = {}
    orr_cap = 1.18 if kind == "totals" else 1.30
    max_price = 4.0 if kind == "totals" else 25.0
    need = ("over", "under") if kind == "totals" else ("home", "away")
    for line, books in pairs.items():
        cands = {}
        for bk, d in books.items():
            o = orr(d)
            if o is None or o > orr_cap:
                continue
            if any(v <= 1.01 or v > max_price for v in d.values()):
                continue
            cands[bk] = d
        min_books = 2 if kind == "totals" else 1
        if len(cands) < min_books:
            continue
        meds = {}
        for s in need:
            meds[s] = med([d[s] for d in cands.values()])
        if any(m is None for m in meds.values()):
            continue
        keep = {}
        for bk, d in cands.items():
            if all(meds[s] / 1.8 <= d[s] <= meds[s] * 1.8 for s in need):
                keep[bk] = d
        if len(keep) < 2:
            keep = cands
        rec = {}
        for s in need:
            vals = sorted(d[s] for d in keep.values())
            rec[s] = {"med": statistics.median(vals), "n": len(vals), "min": vals[0], "max": vals[-1]}
        rec["orr"] = sum(1.0 / rec[s]["med"] for s in need)
        rec["disp"] = (max(rec[need[0]]["med"], rec[need[1]]["med"]) / min(rec[need[0]]["med"], rec[need[1]]["med"]) - 1)
        out[line] = rec
    return out

def parse_old_bets(b):
    oh, ot, oa = {}, {}, {}
    for nm, rec in b.items():
        if nm.startswith("1X2主胜"): oh["home"] = rec
        elif nm.startswith("1X2平局"): oh["draw"] = rec
        elif nm.startswith("1X2客胜"): oh["away"] = rec
        elif nm.startswith("大"): ot["over"] = rec
        elif nm.startswith("小"): ot["under"] = rec
        elif nm.startswith("让球主"):
            mm = re.search(r"[+-]?\d+(?:\.\d+)?", nm)
            oa["home"] = (rec, float(mm.group()) if mm else None)
        elif nm.startswith("让球客"):
            mm = re.search(r"[+-]?\d+(?:\.\d+)?", nm)
            oa["away"] = (rec, float(mm.group()) if mm else None)
    return oh, ot, oa

def ev_calc(p, o):
    try:
        return p * o - 1
    except Exception:
        return None

def pct(a, b):
    try:
        return ("%+.0f%%" % ((b / a - 1) * 100))
    except Exception:
        return ""

def f2(o):
    return ("%.2f" % o) if isinstance(o, (int, float)) else "-"

rows = []
for eid in sorted(targets):
    t, ev = targets[eid], new.get(str(eid))
    old = old_map.get(eid)
    if ev is None or old is None:
        rows.append({"eid": eid, "league": t["league"], "home": t["home"], "away": t["away"], "ko": t["kickoff"], "err": True}); continue
    h2h = best_h2h(ev)
    tots = market_odds(ev, "totals")
    ahs = market_odds(ev, "ah")
    oh, ot, oa = parse_old_bets(old["bets"])
    # 旧主让线(带符号): 让球主(-0.8)=主让0.8
    old_ah_line = (oa.get("home") or ({}, None))[1]
    if ahs and old_ah_line is not None:
        near = sorted(ahs, key=lambda k: abs(k - old_ah_line))
        sel_ah = sorted(near[:2])
    else:
        sel_ah = sorted(ahs)[:2] if ahs else []
    rows.append({"eid": eid, "league": t["league"], "home": t["home"], "away": t["away"], "ko": t["kickoff"],
                 "old_snap": old["snap"], "new_src": ev.get("source"),
                 "old_dir": old["dir_name"], "old_dir_ev": old["dir_ev"], "star": old["star"], "veto": old["veto"],
                 "old_h2h": oh, "old_tot": ot, "old_ah": oa, "old_ah_line": old_ah_line,
                 "new_h2h": h2h, "new_tots": tots, "new_ahs": ahs, "sel_ah": sel_ah})
json.dump(rows, io.open(os.path.join(OUT, "odds_compare_0822_rows.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def dir_new_ev(r):
    d = r["old_dir"]
    if not d:
        return None
    if d.startswith("大") or d.startswith("小"):
        side = "over" if d.startswith("大") else "under"
        main = min(r["new_tots"], key=lambda k: abs(k - 2.5)) if r["new_tots"] else None
        if main is None:
            return None
        ob = r["old_tot"].get(side) or {}
        nv = r["new_tots"][main][side]["med"]
        return (d, ob.get("prob"), ob.get("odds"), nv)
    if d.startswith("1X2"):
        if d.endswith("主胜"): key = "home"
        elif d.endswith("平局"): key = "draw"
        elif d.endswith("客胜"): key = "away"
        else: return None
        ob = r["old_h2h"].get(key) or {}
        if r["new_h2h"] is None:
            return None
        nv = r["new_h2h"]["prices"].get(key)
        return (d, ob.get("prob"), ob.get("odds"), nv)
    if d.startswith("让球"):
        side = "home" if d[2:3] == "主" else "away"
        rec, oline = r["old_ah"].get(side) or ({}, None)
        if oline is None or not r["sel_ah"]:
            return None
        k = min(r["sel_ah"], key=lambda k: abs(k - oline))
        nv = r["new_ahs"][k][side]["med"]
        return (d, rec.get("prob"), rec.get("odds"), nv)
    return None

L = []
L.append("# 08-22 凌晨 27 场 赔率对比（旧快照 08-20 vs 最新拉取 %s）" % PULLED)
L.append("")
L.append("- 旧快照: `scan_window_20260821_ah5.json`（snap=2026-08-20 16:49~17:52 UTC）｜新快照: the-odds-api 23 场 + API-Football 4 场")
L.append("- 方法: 1X2 取最低抽水庄；大小球/让球按庄配对过滤异常价后取跨庄中位价；让球线=带符号主让线")
L.append("- 「旧方向新EV」= 旧模型概率 × 新赔率 − 1（模型概率未重算，只反映盘口移动对价值的影响）")
L.append("")
L.append("## 📊 变化摘要（旧快照 → 最新盘）")
L.append("")
L.append("| 比赛 | 主要变化 | 旧方向 | 旧EV→新EV |")
L.append("|---|---|---|---|")
for r in rows:
    if r.get("err"):
        continue
    notes = []
    if r["new_h2h"]:
        for side, lbl in (("home", "主胜"), ("draw", "平局"), ("away", "客胜")):
            ob = r["old_h2h"].get(side) or {}
            ov, nv = ob.get("odds"), r["new_h2h"]["prices"].get(side)
            if ov and nv and abs(nv / ov - 1) >= 0.05:
                notes.append("1X2%s%s" % (lbl, pct(ov, nv)))
    if r["new_tots"]:
        main = min(r["new_tots"], key=lambda k: abs(k - 2.5))
        if main != 2.5:
            notes.append("大小球主盘2.5→%g" % main)
        else:
            ob = r["old_tot"].get("over") or {}
            if ob.get("odds"):
                chg = r["new_tots"][main]["over"]["med"] / ob["odds"] - 1
                if abs(chg) >= 0.05:
                    notes.append("大球盘%s" % pct(ob["odds"], r["new_tots"][main]["over"]["med"]))
    if r["old_ah_line"] is not None and r["new_ahs"]:
        near = min(r["new_ahs"], key=lambda k: abs(k - r["old_ah_line"]))
        if abs(near - r["old_ah_line"]) >= 0.01:
            notes.append("让球线%+.2f→%+.2f" % (r["old_ah_line"], near))
    dn = dir_new_ev(r)
    if dn:
        d, p, ov, nv = dn
        ev_o = ev_calc(p, ov); ev_n = ev_calc(p, nv)
        ev_txt = "%+.1f%%→%+.1f%%" % ((ev_o or 0) * 100, (ev_n or 0) * 100)
        if (ev_o or 0) * (ev_n or 0) < 0 or abs((ev_n or 0) - (ev_o or 0)) > 0.1:
            ev_txt = "**" + ev_txt + "**"
    else:
        ev_txt = "-"
    L.append("| %s %s vs %s | %s | %s | %s |" % (r["league"], r["home"], r["away"], "；".join(notes) or "基本不变", r["old_dir"] or "-", ev_txt))
L.append("")
for r in rows:
    if r.get("err"):
        L.append("## ❌ %s | %s vs %s（数据缺失）" % (r["league"], r["home"], r["away"])); L.append(""); continue
    L.append("## %s | %s vs %s（%s）" % (r["league"], r["home"], r["away"], r["ko"]))
    L.append("")
    L.append("旧方向: **%s**（旧EV %+.1f%%）｜旧snap %s｜新源 %s" % (
        r["old_dir"] or "-", (r["old_dir_ev"] or 0) * 100, r["old_snap"], r["new_src"]))
    L.append("")
    if r["new_h2h"]:
        nh = r["new_h2h"]
        L.append("### 1X2（最低抽水庄: %s, 抽水 %.3f）" % (nh["book"], nh["orr"]))
        L.append("| 结果 | 旧赔率 | 新赔率 | 变化 | 旧EV | 新EV |")
        L.append("|---|---|---|---|---|---|")
        for side, lbl in (("home", "主胜"), ("draw", "平局"), ("away", "客胜")):
            ob = r["old_h2h"].get(side) or {}
            ov, nv = ob.get("odds"), (nh["prices"] or {}).get(side)
            L.append("| %s | %s | %s | %s | %+.1f%% | %+.1f%% |" % (
                lbl, f2(ov), f2(nv), pct(ov, nv), (ev_calc(ob.get("prob"), ov) or 0) * 100, (ev_calc(ob.get("prob"), nv) or 0) * 100))
    else:
        L.append("### 1X2: 新盘口无 h2h 数据")
    L.append("")
    if r["new_tots"]:
        main = min(r["new_tots"], key=lambda k: abs(k - 2.5))
        L.append("### 大小球（新盘口线位: %s；主盘按 %g）" % (", ".join("%g" % k for k in sorted(r["new_tots"])), main))
        L.append("| 方向 | 旧线/赔率 | 新线/赔率 | 变化 | 旧EV | 新EV |")
        L.append("|---|---|---|---|---|---|")
        for side, lbl in (("over", "大球"), ("under", "小球")):
            ob = r["old_tot"].get(side) or {}
            ov, nv = ob.get("odds"), r["new_tots"][main][side]["med"]
            L.append("| %s | 2.5 / %s | %g / %s | %s | %+.1f%% | %+.1f%% |" % (
                lbl, f2(ov), main, f2(nv), pct(ov, nv),
                (ev_calc(ob.get("prob"), ov) or 0) * 100, (ev_calc(ob.get("prob"), nv) or 0) * 100))
        if main != 2.5:
            L.append("> 注: 新盘口未挂 2.5 线（当前主盘 %g），新旧不同线 EV 仅参考" % main)
        if r["new_tots"][main]["disp"] > 0.12:
            L.append("> ⚠ 大小球跨庄分歧大（大/小中位比 %.2f），参考度下调" % (r["new_tots"][main]["disp"] + 1))
    else:
        L.append("### 大小球: 新盘口无数据")
    L.append("")
    if r["sel_ah"]:
        L.append("### 让球（新盘口全部线位: %s；下表为最接近旧主让线 %+.2f 的盘）" % (
            ", ".join("%+.2f" % k for k in sorted(r["new_ahs"])),
            r["old_ah_line"] if r["old_ah_line"] is not None else 0))
        L.append("| 方向 | 旧线/赔率 | 新线/赔率 | 变化 | 旧EV | 新EV |")
        L.append("|---|---|---|---|---|---|")
        for k in r["sel_ah"]:
            na = r["new_ahs"][k]
            for side, lbl in (("home", "主让"), ("away", "客让")):
                rec, oline = r["old_ah"].get(side) or ({}, None)
                ov, nv = rec.get("odds"), na[side]["med"]
                old_line = oline if oline is not None else 0
                new_line = k if side == "home" else -k
                L.append("| %s | %+.2f / %s | %+.2f / %s | %s | %+.1f%% | %+.1f%% |" % (
                    lbl, old_line, f2(ov), new_line, f2(nv), pct(ov, nv),
                    (ev_calc(rec.get("prob"), ov) or 0) * 100, (ev_calc(rec.get("prob"), nv) or 0) * 100))
    else:
        L.append("### 让球: 新盘口无数据")
    L.append("")

md = "\n".join(L)
out_md = os.path.join(OUT, "odds_compare_0822_27.md")
io.open(out_md, "w", encoding="utf-8").write(md)
print("saved:", out_md, "| rows:", len(rows))
