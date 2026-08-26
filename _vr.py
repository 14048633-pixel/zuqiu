import json,io,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for f in ["refetch5_results_20260817.json","refetch16_results_20260817.json"]:
    d=json.load(io.open("analysis_records/"+f,encoding="utf-8"))
    print("=== %s ===" % f)
    for r in d["results"]:
        if not r.get("ok"): continue
        t=r["target"]
        print("%s | %s vs %s | dir=%s EV%+.1f%% | veto=%s | %s" % (
            t["league"], t["home"], t["away"], r["direction"], r["ev"], r["vetoed"], (r.get("veto_reason") or "")[:40]))
