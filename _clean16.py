import json,io,os,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
p=r"D:\足球分析\analysis_records\refetch16_results_20260817.json"
d=json.load(io.open(p,encoding="utf-8"))
seen={}
for rr in d["results"]:
    t=rr["target"]
    key=(t["league"],t["home"],t["away"])
    # 保留 ok 的；同一 target 多条目保留最后一个 ok
    if rr.get("ok"):
        seen[key]=rr
clean={"ts":d["ts"],"results":list(seen.values())}
io.open(p,"w",encoding="utf-8").write(json.dumps(clean,ensure_ascii=False,indent=1))
print("clean:",len(clean["results"]),"| ok:",sum(1 for x in clean["results"] if x.get("ok")))
