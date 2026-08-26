# -*- coding: utf-8 -*-
import sys, json
sys.stdout.reconfigure(encoding="utf-8")
f = json.load(open(r"D:\足球分析\analysis_records\research\odds_live_0822_matched_final.json", encoding="utf-8"))
ev = f["matches"]["209535"]  # Arsenal
bk0 = ev["bookmakers"][0]
print("BOOK:", bk0.get("key"), bk0.get("title"))
for mk in bk0.get("markets") or []:
    print("  MARKET:", mk.get("key"), "| n_out:", len(mk.get("outcomes") or []))
    for oc in (mk.get("outcomes") or [])[:6]:
        print("     oc:", json.dumps(oc, ensure_ascii=False))
print("===== AFB =====")
ev2 = f["matches"]["211687"]  # Cherno More
bk1 = (ev2.get("bookmakers") or [])[0]
print("AFB BOOK:", bk1.get("name"))
for b in bk1.get("bets") or []:
    print("  BET:", b.get("name"), "| n_val:", len(b.get("values") or []))
    for v in (b.get("values") or [])[:6]:
        print("     val:", json.dumps(v, ensure_ascii=False))
