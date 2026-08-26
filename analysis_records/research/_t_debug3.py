# -*- coding: utf-8 -*-
import sys, json, re
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"D:\足球分析\analysis_records\research")
# 直接内联 _compare_odds_0822.py 中的 market_odds 定义
import importlib.util
spec = importlib.util.spec_from_file_location("cmp", r"D:\足球分析\analysis_records\research\_compare_odds_0822.py")
# 不执行整个脚本; 手动复制函数
def uniq(s):
    return re.sub(r"[^a-z0-9 ]", "", (str(s or "")).lower()).strip()
def parse_afb_bets(bk):
    out = {}
    for b in bk.get("bets") or []:
        vals = {}
        for v in b.get("values") or []:
            try:
                vals[str(v.get("value"))] = float(v.get("odd"))
            except Exception:
                pass
        out[(b.get("name") or "")] = vals
    return out
def market_odds(ev, kind):
    res = {}
    is_afb = ev.get("source") == "api-football"
    h, a = uniq(ev.get("home_team")), uniq(ev.get("away_team"))
    for bk in ev.get("bookmakers") or []:
        if is_afb:
            pb = parse_afb_bets(bk)
            for nm, vals in pb.items():
                if kind == "totals" and "over/under" in nm.lower():
                    for v, p in vals.items():
                        mm = re.match(r"^\s*(Over|Under)\s+(\d+(?:\.\d+)?)\s*$", v, re.I)
                        if mm:
                            res.setdefault(float(mm.group(2)), {}).setdefault("over" if mm.group(1).lower() == "over" else "under", []).append((p, bk.get("name")))
                elif kind == "ah" and "handicap" in nm.lower():
                    for v, p in vals.items():
                        mm = re.match(r"^\s*(Home|Away)\s+([+-]\d+(?:\.\d+)?)\s*$", v)
                        if mm:
                            res.setdefault(float(mm.group(2)), {}).setdefault("home" if mm.group(1).lower() == "home" else "away", []).append((p, bk.get("name")))
        else:
            for mk in bk.get("markets") or []:
                key = mk.get("key")
                if kind == "totals" and key != "totals": continue
                if kind == "ah" and key != "spreads": continue
                for oc in mk.get("outcomes") or []:
                    nm = uniq(oc.get("name")); low = str(oc.get("name", "")).lower()
                    pt = oc.get("point")
                    if pt is None: continue
                    try: line = float(pt)
                    except Exception: continue
                    if kind == "totals":
                        if low.startswith("over"): side = "over"
                        elif low.startswith("under"): side = "under"
                        else: continue
                    else:
                        if nm == h: side = "home"
                        elif nm == a: side = "away"
                        else: continue
                    res.setdefault(line, {}).setdefault(side, []).append((oc.get("price"), bk.get("key") or bk.get("title")))
    out = {}
    for line, sides in res.items():
        rec = {}
        ok = True
        for side in (("over", "under") if kind == "totals" else ("home", "away")):
            lst = sides.get(side) or []
            if not lst: ok = False; break
            prices = sorted(p for p, _ in lst if p)
            rec[side] = {"best": prices[-1], "med": prices[len(prices)//2], "n": len(lst)}
        if ok:
            rec["orr"] = sum(1.0 / max(float(v), 1e-9) for v in (rec[s]["best"] for s in (("over","under") if kind=="totals" else ("home","away"))))
            out[line] = rec
    return out

f = json.load(open(r"D:\足球分析\analysis_records\research\odds_live_0822_matched_final.json", encoding="utf-8"))
ev = f["matches"]["211321"]
out = market_odds(ev, "ah")
print("AH keys:", sorted(out))
for k in sorted(out):
    print(" ", k, out[k])
