import json,io,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d=json.load(io.open("analysis_records/refetch5_results_20260817.json",encoding="utf-8"))
for r in d["results"]:
    if not r.get("ok"): 
        print("ERR", r); continue
    t=r["target"]
    print("== %s %s vs %s" % (t["league"], t["home"], t["away"]))
    print("  snap_age_h=%s dir=%s prob=%s odds=%s EV=%s%%" % (r["snap_age_h"], r["direction"], r["dir_prob"], r["dir_odds"], r["ev"]))
    print("  veto=%s reason=%s" % (r["vetoed"], r.get("veto_reason")))
    print("  star=%s tier=%s risk=%s" % (r["star"], r["ev_tier"], r["risk_tags"]))
    print("  lambda=%s wdl=%s" % (r["lambda"], r["wdl"]))
    print("  bets:", [(b["name"], b["prob"], b["odds"], b["ev"]) for b in r["bets"]])
