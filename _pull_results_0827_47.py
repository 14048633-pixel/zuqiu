# -*- coding: utf-8 -*-
"""拉取 27号47场 赛果 (BSD event detail) -> analysis_records/results_scan_20260827_final.json"""
import io, sys, os, json, time
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
import bsd_extra
BJT = timezone(timedelta(hours=8))

def main():
    lst = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan24h_20260827_1947.json"), encoding="utf-8"))["matches"]
    print("目标场次:", len(lst))
    rows = []
    done = pending = err = 0
    for i, m in enumerate(lst):
        eid = m["id"]
        try:
            j = bsd_extra._get("/api/v2/events/%d/" % eid)
        except Exception as e:
            j = None
            print("  [%d/%d] ERR %s vs %s: %s" % (i+1, len(lst), m["home"], m["away"], repr(e)[:100]))
        if not isinstance(j, dict):
            err += 1
            rows.append({"id": eid, "home": m["home"], "away": m["away"],
                         "ko_bjt": m.get("kickoff"), "status": "unknown", "error": "BSD detail None"})
            time.sleep(0.3)
            continue
        st = j.get("status") or "unknown"
        if st == "finished":
            done += 1
        else:
            pending += 1
        ss = bsd_extra.event_settle_scores(j)
        rows.append({
            "id": eid, "home": m["home"], "away": m["away"],
            "ko_bjt": m.get("kickoff"),
            "status": st,
            "home_score": j.get("home_score"), "away_score": j.get("away_score"),
            "home_ht": j.get("home_score_ht"), "away_ht": j.get("away_score_ht"),
            "extra_time": j.get("extra_time_score"),
            "penalty": j.get("penalty_shootout"),
            "minute": j.get("current_minute"),
            "period": ss["period"],
            "is_aet": ss["is_aet"],
            "settle_home_score": ss["hg_90"],
            "settle_away_score": ss["ag_90"],
            "needs_90_verify": ss["needs_verify"],
        })
        if ss["needs_verify"]:
            print("  [AET] %s vs %s period=%s 比分%s:%s为加时后全场, 90分钟比分需权威源补录" % (
                m["home"], m["away"], ss["period"], j.get("home_score"), j.get("away_score")))
        time.sleep(0.3)
    ts = datetime.now(BJT).strftime("%Y%m%d_%H%M")
    fp = os.path.join(ROOT, "analysis_records", "results_scan_20260827_47_%s.json" % ts)
    json.dump({"generated": datetime.now(BJT).isoformat(), "n": len(rows),
               "finished": done, "pending": pending, "error": err, "matches": rows},
              io.open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved ->", fp)
    print("finished:", done, "| pending(未结束/取消):", pending, "| error:", err)
    for r in rows:
        if r["status"] != "finished":
            print("  未结束:", r["ko_bjt"], r["home"], "vs", r["away"], "|", r["status"])
if __name__ == "__main__":
    main()
