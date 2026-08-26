import json,io,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d=json.load(io.open("analysis_records/48h_plan_20260817.json",encoding="utf-8"))
nomodel=[r for r in d["rows"] if r["model_ev"]=="无"]
hasmodel=[r for r in d["rows"] if r["model_ev"]!="无"]
print("无模型 %d 场:" % len(nomodel))
for r in nomodel:
    print("  %s | %s vs %s | 置信%s | 来源%s" % (r["kickoff"], r["home"], r["away"], r["conf"], r["src"]))
print("有模型 %d 场:" % len(hasmodel))
for r in hasmodel:
    print("  %s | %s vs %s | %s EV%s | %s" % (r["kickoff"], r["home"], r["away"], r["model_leg"], r["model_ev"], "重算" if r.get("refetched") else "原扫描"))
