import json,io,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d=json.load(io.open("analysis_records/live_odds_48h_20260817.json",encoding="utf-8"))
for m in d["matches"]:
    if m.get("league") in ("丹超","阿甲"):
        print(m["league"], m["home"],"vs",m["away"])
        print("  ct=",m.get("ct"),"h2h=",m.get("h2h"),"ou25=",m.get("ou25"))
        print("  fair_1x2=",m.get("fair_1x2"),"dir=",m.get("dir_1x2"))
        print("  fair_ou=",m.get("fair_ou"),"dir=",m.get("dir_ou"))
