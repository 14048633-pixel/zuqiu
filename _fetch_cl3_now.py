# -*- coding: utf-8 -*-
"""3场欧冠资格赛 最新赔率快照 + 方向重算 v2 (加API名匹配)"""
import io, os, sys, json
from datetime import datetime, timezone, timedelta

ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2", "src"))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, os.path.join(ROOT, "form_phase0"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from live_odds import fetch_league_odds, flatten_events, append_snapshots, snapshots_path
from fetch_live_48h import simpl
import scan_upcoming as SU

TARGETS = [
    {"league": "欧冠资格", "home": "GNK Dinamo Zagreb", "away": "Viking FK", "api": ("Dinamo Zagreb", "Viking FK")},
    {"league": "欧冠资格", "home": "Fenerbahçe", "away": "Olympique Lyonnais", "api": ("Fenerbahce", "Lyon")},
    {"league": "欧冠资格", "home": "Levski Sofia", "away": "AEK Athens", "api": ("PFC Levski Sofia", "AEK Athens")},
]

def load_key():
    env = {}
    for line in io.open(os.path.join(ROOT, ".env"), encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1); env[k.strip()] = v.split("#")[0].strip()
    return env.get("ODDS_API_KEY_3") or env.get("ODDS_API_KEY")

def main():
    key = load_key()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    events, quota = fetch_league_odds(key, "soccer_uefa_champs_league_qualification",
                                      markets="h2h,totals,spreads", regions="eu,uk,us", timeout=40)
    print("欧冠资格 events: %d | remaining=%s" % (len(events or []), (quota or {}).get("remaining")))
    if not events:
        print("NO EVENTS"); return
    rows = flatten_events(events, "欧冠资格", ts)
    append_snapshots(snapshots_path(base_dir=os.path.join(ROOT, "prediction_v2")), rows)

    team_stats, lavg, index = SU.load_team_stats()
    events_p, future_skipped = SU.parse_snapshots()
    idx = {}
    for ev in events_p:
        idx.setdefault((ev["league"], simpl(ev["home"]), simpl(ev["away"])), ev)
        idx.setdefault((ev["league"], simpl(ev["away"]), simpl(ev["home"])), ev)

    out = []
    for t in TARGETS:
        api_h, api_a = t.get("api") or (t["home"], t["away"])
        rec = idx.get((t["league"], simpl(api_h), simpl(api_a))) or \
              idx.get((t["league"], simpl(api_a), simpl(api_h)))
        if rec is None:
            out.append({"target": t, "ok": False, "err": "未找到事件 (%s vs %s)" % (api_h, api_a)})
            print("MISS", t["home"], "vs", t["away"]); continue
        try:
            r = SU.analyze_match(rec, team_stats, lavg, index)
            d = r.get("direction") or {}
            bb = r.get("best_bet")
            out.append({
                "target": t, "ok": True,
                "event_home": rec["home"], "event_away": rec["away"],
                "snap": str(rec["snap"]), "snap_age_h": round(r.get("snap_age_h", -1), 1),
                "lambda": r.get("lambda", {}), "wdl": r.get("wdl", {}),
                "direction": d.get("name"), "dir_prob": round((d.get("prob") or 0) * 100, 1),
                "dir_odds": d.get("odds"), "ev": round((d.get("ev") or 0) * 100, 1),
                "market_fair": d.get("market_fair"), "vetoed": d.get("vetoed"),
                "veto_reason": d.get("veto_reason"), "star": r.get("star"),
                "ev_tier": r.get("ev_tier"), "risk_tags": r.get("risk_tags"),
                "best_bet": (bb.get("name"), round((bb.get("prob") or 0) * 100, 1), bb.get("odds"),
                             round((bb.get("ev") or 0) * 100, 1)) if bb else None,
                "bets": [{"name": b["name"], "prob": round(b["prob"] * 100, 1), "odds": b["odds"],
                          "ev": round(b["ev"] * 100, 1)} for b in r.get("bets", [])],
            })
            print("OK %s vs %s | dir=%s(%.1f%%) | odds=%s | EV=%s%% | veto=%s | star=%s" % (
                rec["home"], rec["away"], d.get("name"), (d.get("prob") or 0) * 100,
                d.get("odds"), round((d.get("ev") or 0) * 100, 1), d.get("vetoed"), r.get("star")))
        except Exception as e:
            import traceback; traceback.print_exc()
            out.append({"target": t, "ok": False, "err": str(e)[:200]})

    fp = os.path.join(ROOT, "analysis_records", "live_cl3_%s.json" % datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M"))
    io.open(fp, "w", encoding="utf-8").write(json.dumps({"ts": ts, "quota": quota, "results": out}, ensure_ascii=False, indent=1))
    print("saved", fp, "| ok:", sum(1 for x in out if x.get("ok")), "/", len(out))

if __name__ == "__main__":
    main()
