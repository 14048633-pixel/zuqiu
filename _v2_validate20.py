# -*- coding: utf-8 -*-
import json, io, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\足球分析\prediction_v2")
from draw_warning import draw_warning_score, draw_warning_label

rows = json.load(io.open(r"D:\足球分析\_rows20.json", encoding="utf-8"))
out = []
for r in rows:
    info = {"league": r["league"], "h2h": r.get("h2h"),
            "resonance": r.get("resonance") or "",
            "model_leg": r.get("model_leg") or "",
            "form": r.get("form") or "中性"}
    sc, tags = draw_warning_score(info)
    out.append({"kickoff": r["kickoff"], "league": r["league"], "match": "%s vs %s" % (r["home"], r["away"]),
                "dp": (r.get("h2h") or [None])[1] if r.get("h2h") and len(r["h2h"]) >= 2 else None,
                "sc": sc, "label": draw_warning_label(sc), "tags": tags,
                "form": r.get("form"), "resonance": r.get("resonance"),
                "pick": r.get("pick"), "conf": r.get("conf")})

import collections
print("== 当日 20 场 v2 预警分布 ==")
for lb in ["防平高危", "防平提醒", "平局观察", ""]:
    grp = [x for x in out if x["label"] == lb]
    print("%s: %d 场" % (lb or "无预警", len(grp)))
print()
for x in sorted(out, key=lambda z: -z["sc"]):
    print("%s | %s | %s | %s | 平赔%s | %d分 %s | form=%s" % (
        x["kickoff"], x["league"], x["match"], x["pick"], x["dp"], x["sc"], x["label"], x["form"]))
    if x["tags"]:
        print("    信号: " + " / ".join(x["tags"]))
