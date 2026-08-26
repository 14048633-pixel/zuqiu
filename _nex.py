import json,io,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d=json.load(io.open("analysis_records/refetch16_results_20260817.json",encoding="utf-8"))
for r in d["results"]:
    if not r.get("ok"): continue
    if "Necaxa" in r["target"]["home"] or "Necaxa" in str(r.get("event_home","")):
        print(json.dumps(r,ensure_ascii=False,indent=1))
