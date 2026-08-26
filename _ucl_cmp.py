# -*- coding: utf-8 -*-
import io, json
ROOT = r"D:\足球分析"
def load(fn):
    return json.load(io.open(ROOT + r"\analysis_records\\" + fn, encoding="utf-8"))

mev = {r["id"]: r for r in load("key46_model_ev_20260818_2316.json")}
v2  = {r["id"]: r for r in load("key46_ev_v2_20260818_2317.json")}
v3  = {r["id"]: r for r in load("key46_ev_v3_20260818_2319.json")}
fin = {r["id"]: r for r in load("key46_ev_final_20260818_2319.json")}
fin2= {r["id"]: r for r in load("key46_ev_final2_20260818_2319.json")}
key = {r["id"]: r for r in load("key46_20260818_2307.json")["results"]}

ucl = [r for r in key.values() if r["league"]=="欧冠"]
ucl.sort(key=lambda r: r["kickoff"])
for t in ucl:
    i = t["id"]; h, a = t["home"], t["away"]
    m = mev.get(i, {}); vv2 = v2.get(i, {}); vv3 = v3.get(i, {}); ff = fin.get(i, {}); f2 = fin2.get(i, {})
    bo = t.get("bsd_ou25") or {}
    to = (t.get("to") or {}).get("ou25") or {}
    print("== %s | %s vs %s" % (t["kickoff"], h, a))
    print("   旧rawλ: %s  模型OU: %s(%.0f%%) EV%.1f%%" % (m.get("lam"), m.get("model_ou"), m.get("model_ou_prob") or 0, (m.get("ev_ou") or 0)*100))
    print("   ev_v2 : λ%s OU %s | ev_v3: our %s bsd %s | final: our %s bsd %s | final2: our %s bsd %s" % (
        vv2.get("lam"), vv2.get("model_ou"),
        vv3.get("our_ou"), vv3.get("ou_dir"),
        ff.get("our_ou"), ff.get("ou_dir"),
        f2.get("our_ou"), f2.get("ou_dir")))
    print("   BSD市场: %s %.0f%% (盘 %s/%s) | the-odds: %s %.0f%%" % (
        bo.get("dir"), bo.get("prob") or 0,
        (t.get("bsd_odds") or {}).get("over_25_goals"), (t.get("bsd_odds") or {}).get("under_25_goals"),
        to.get("dir"), to.get("dir_prob") or 0))
