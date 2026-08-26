# -*- coding: utf-8 -*-
"""scan24h 有价值比赛批量分析 + 生成 MD 报告"""
import sys, os, json, io, re, unicodedata, difflib, collections, glob
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
import scan_upcoming as su

BJT = timezone(timedelta(hours=8))
SNAP = os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv")

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def name_sim(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if len(na) >= 6 and len(nb) >= 6 and (na in nb or nb in na):
        return 0.86
    r = difflib.SequenceMatcher(None, na, nb).ratio()
    ta = set(re.findall(r"[a-z0-9]{3,}", na)); tb = set(re.findall(r"[a-z0-9]{3,}", nb))
    j = len(ta & tb) / len(ta | tb) if (ta | tb) else 0.0
    return max(r, j)

def find_scan():
    cands = sorted(glob.glob(os.path.join(ROOT, "analysis_records", "scan24h_valuable_*.json")), key=os.path.getmtime)
    return cands[-1] if cands else None

def main():
    scan_path = None
    if "--scan" in sys.argv:
        i = sys.argv.index("--scan")
        if i + 1 < len(sys.argv):
            scan_path = sys.argv[i + 1]
    scan_path = scan_path or find_scan()
    scan = json.load(open(scan_path, encoding="utf-8"))
    val_matches = scan["matches"]
    ts, lavg, index = su.load_team_stats()
    out, _ = su.parse_snapshots(SNAP)

    exact_idx = {}
    for e in out:
        exact_idx.setdefault((e["league"], norm(e["home"]), norm(e["away"])), []).append(e)

    rows, unmatched, mapped = [], [], collections.Counter()
    used = set()
    for vm in val_matches:
        vm_kt = datetime.fromisoformat(vm["kickoff_iso"].replace("Z", "+00:00"))
        cands = exact_idx.get((vm["league"], norm(vm["home"]), norm(vm["away"])), [])
        best, best_score = None, 0.0
        if not cands:
            for e in out:
                if abs((e["ct"] - vm_kt).total_seconds()) > 4 * 3600:
                    continue
                sc = min(name_sim(vm["home"], e["home"]), name_sim(vm["away"], e["away"])) * 0.7
                sc += 0.3 if e["league"] == vm["league"] else 0.0
                sc += 0.1 if abs((e["ct"] - vm_kt).total_seconds()) <= 1800 else 0.0
                if sc > best_score:
                    best, best_score = e, sc
            if best and best_score >= 0.62:
                cands = [best]
        if cands:
            cands = [c for c in cands if id(c) not in used]
            if cands:
                cands.sort(key=lambda c: (bool(c.get("h2h")) + bool(c.get("spread")) + bool(c.get("totals")), c.get("snap", "")), reverse=True)
                e = cands[0]; used.add(id(e))
                if e["league"] != vm["league"]:
                    mapped[vm["league"] + "→" + e["league"]] += 1
                m = {"id": vm["id"], "league": e["league"], "home": vm["home"], "away": vm["away"],
                     "ct": e["ct"], "snap": e["snap"], "h2h": e.get("h2h"), "spread": e.get("spread"),
                     "totals": e.get("totals")}
                try:
                    r = su.analyze_match(m, ts, lavg, index)
                except Exception as ex:
                    r = {"error": "analyze_match异常: %r" % ex, "risk_tags": [], "notes": []}
                rows.append((vm_kt, vm, e, r))
                continue
        unmatched.append(vm)

    rows.sort(key=lambda x: x[0])
    out_rows = []
    for vm_kt, vm, e, r in rows:
        di, bb = r.get("direction"), r.get("best_bet")
        rec = {
            "ct": vm_kt.astimezone(BJT).strftime("%m-%d %H:%M"),
            "league": r.get("league") or vm["league"],
            "home": vm["home"], "away": vm["away"],
            "odds_home": e["home"], "odds_away": e["away"], "odds_league": e["league"],
            "lambda": r.get("lambda"), "wdl": r.get("wdl"), "market_fair": r.get("market_fair"),
            "data_src": r.get("data_src"), "snap_age_h": r.get("snap_age_h"),
            "direction": di, "best_bet": bb, "star": r.get("star"), "ev_tier": r.get("ev_tier"),
            "dir_consistency": r.get("dir_consistency"), "risk_tags": r.get("risk_tags", []),
            "draw_warn": r.get("draw_warn"), "upset": r.get("upset"),
            "notes": r.get("notes", []), "error": r.get("error"), "bets": r.get("bets"),
        }
        out_rows.append(rec)

    now = datetime.now(BJT)
    outp = os.path.join(ROOT, "analysis_records", "scan24h_analysis_%s.json" % now.strftime("%Y%m%d_%H%M"))
    res = {
        "title": "%s | 有价值分析" % scan.get("title", ""),
        "ts": now.isoformat(), "window_start": scan.get("window_start"), "window_end": scan.get("window_end"),
        "n_scan": len(val_matches), "n_analyzed": len(out_rows), "n_no_odds": len(unmatched),
        "mapped_league_fixes": dict(mapped),
        "matches": out_rows,
        "unmatched": [{"league": u["league"], "home": u["home"], "away": u["away"], "kickoff_iso": u["kickoff_iso"]} for u in unmatched],
    }
    json.dump(res, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved:", outp)
    print("共%d场 | 分析%d | 无赔率%d | 联赛映射修正:%s" % (len(val_matches), len(out_rows), len(unmatched), dict(mapped) or "无"))

if __name__ == "__main__":
    main()
