# -*- coding: utf-8 -*-
"""BSD 拉取比赛结果 v3: match_package 里的 BSD id -> /api/v2/events/{id}/ 拿最终比分"""
import sys, os, io, json, glob, re, unicodedata
from datetime import datetime, timezone, timedelta

ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, ROOT)
from bsd_extra import _get

BJT = timezone(timedelta(hours=8))

def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

def _fuzzy(a, b):
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    wa, wb = set(na.split()), set(nb.split())
    if wa and wb and (wa <= wb or wb <= wa):
        return 0.9
    from difflib import SequenceMatcher
    return SequenceMatcher(None, na, nb).ratio()

def load_alias():
    try:
        return json.load(io.open(os.path.join(ROOT, "strategy_data", "teams_alias.json"), encoding="utf-8")).get("alias", {})
    except Exception:
        return {}
ALIAS = load_alias()

def cands(name):
    out = [name]
    c = ALIAS.get(name)
    if c and c not in out:
        out.append(c)
    return out

def build_pkg_index():
    pkgs = []
    for fp in glob.glob(os.path.join(ROOT, "analysis_records", "match_package", "*.json")):
        try:
            d = json.load(io.open(fp, encoding="utf-8"))
        except Exception:
            continue
        if d.get("id") is not None:
            pkgs.append(d)
    return pkgs

def match_pkg(m, pkgs):
    best = None; bs = 0.0
    for d in pkgs:
        sh = max((_fuzzy(h, d.get("home") or "") for h in cands(m["home"])), default=0)
        sa = max((_fuzzy(a, d.get("away") or "") for a in cands(m["away"])), default=0)
        s = (sh + sa) / 2
        if s > bs:
            bs = s; best = d
    return (best, bs) if best and bs >= 0.7 else (None, bs)

def main():
    fs = sorted(glob.glob(os.path.join(ROOT, "analysis_records", "scan_next24h_*.json")), key=os.path.getmtime)
    d = json.load(io.open(fs[-1], encoding="utf-8"))
    pkgs = build_pkg_index()
    print("扫描文件:", os.path.basename(fs[-1]), "| 场次:", len(d), "| match_package:", len(pkgs))
    out = []
    for m in d:
        pkg, s = match_pkg(m, pkgs)
        row = {"ko_bjt": m["ko_bjt"], "league": m["league"], "home": m["home"], "away": m["away"],
               "best_bet": (m.get("best_bet") or {}).get("name"),
               "bb_ev": (m.get("best_bet") or {}).get("ev"),
               "bsd_id": None, "status": "无BSD包", "score": None, "match_score": round(s, 2)}
        if pkg:
            row["bsd_id"] = pkg.get("id")
            det = _get("/api/v2/events/%s/" % pkg["id"])
            if det:
                hs, as_ = det.get("home_score"), det.get("away_score")
                row["status"] = det.get("status")
                row["score"] = ("%s-%s" % (hs, as_)) if hs is not None else None
        out.append(row)
    jp = os.path.join(ROOT, "analysis_records", "results_bsd_%s.json" % datetime.now(BJT).strftime("%Y%m%d_%H%M"))
    json.dump(out, io.open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved", jp)
    print()
    print("== 已结束 ==")
    n = 0
    for r in out:
        if r["status"] == "finished" and r["score"]:
            n += 1
            print("%-6s %-8s %-26s %-6s %-8s %s" % (r["ko_bjt"], r["league"], r["home"] + " vs " + r["away"], r["score"], r["best_bet"] or "", "★" if r["best_bet"] else ""))
    print("已结束:", n)
    print()
    print("== 未结束/未匹配 ==")
    for r in out:
        if not (r["status"] == "finished" and r["score"]):
            print("%-6s %-8s %-26s %-12s %-6s id=%s" % (r["ko_bjt"], r["league"], r["home"] + " vs " + r["away"], r["status"], r["score"] or "", r["bsd_id"]))

if __name__ == "__main__":
    main()
