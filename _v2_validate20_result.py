# -*- coding: utf-8 -*-
import json, io, sys, unicodedata
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\足球分析\prediction_v2")
from draw_warning import draw_warning_score, draw_warning_label

TR = {"ø":"o","Ø":"O","å":"a","Å":"A","æ":"ae","Æ":"AE","č":"c","š":"s","ž":"z","é":"e","í":"i","ó":"o","ú":"u","ü":"u","ö":"o","á":"a","ñ":"n","ã":"a","õ":"o"}
def norm(s):
    s = str(s)
    for k, v in TR.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return "".join(c for c in s if c.isalnum())

rows = json.load(io.open(r"D:\足球分析\_rows20.json", encoding="utf-8"))
results = [
    ("Pisa","Empoli","1-1"), ("Sassuolo","Cesena","3-0"),
    ("Brøndby IF","Sønderjyske Fodbold","3-2"), ("BK Häcken","Halmstads BK","1-0"),
    ("Sporting Gijón","CE Sabadell","0-0"), ("Estudiantes de Río Cuarto","Atlético Tucumán","0-1"),
    ("Samsunspor","Göztepe","3-3"), ("Cremonese","Sampdoria","2-0"),
    ("Cardiff City","Wrexham","1-1"), ("Deportivo de A Coruña","Elche","1-1"),
    ("Palermo","Lecce","2-0"), ("Casa Pia","Benfica","0-7"),
    ("Almería","CD Eldense","3-0"), ("CA Lanús","CA Independiente","1-3"),
    ("Vélez Sarsfield","Defensa y Justicia","1-1"), ("Internacional","Remo","1-1"),
    ("Palestino","Huachipato","5-1"), ("Gimnasia y Esgrima Mendoza","CA Talleres","3-1"),
    ("Club Necaxa","Club León","1-2"), ("CF Pachuca","Club Puebla","2-3"),
]
res_idx = {}
for h, a, sc in results:
    res_idx[(norm(h), norm(a))] = sc
    res_idx[(norm(a), norm(h))] = sc

out = []
for r in rows:
    info = {"league": r["league"], "h2h": r.get("h2h"),
            "resonance": r.get("resonance") or "",
            "model_leg": r.get("model_leg") or "",
            "form": r.get("form") or "中性"}
    sc, tags = draw_warning_score(info)
    scr = res_idx.get((norm(r["home"]), norm(r["away"]))) or "?"
    parts = scr.split("-") if scr != "?" else []
    is_draw = len(parts) == 2 and parts[0] == parts[1]
    out.append({"ko": r["kickoff"], "lg": r["league"], "m": "%s vs %s" % (r["home"], r["away"]),
                "dp": (r.get("h2h") or [None])[1] if r.get("h2h") and len(r["h2h"]) >= 2 else None,
                "sc": sc, "label": draw_warning_label(sc), "score": scr, "draw": is_draw,
                "tags": tags})

print("== 当日20场 v2预警 vs 实际平局 ==")
for x in sorted(out, key=lambda z: -z["sc"]):
    mark = "**平局**" if x["draw"] else "非平"
    print("%s | %-4s | %-40s | 平赔%-4s | %d分 %-5s | %s %s" % (
        x["ko"], x["lg"], x["m"], x["dp"], x["sc"], x["label"], mark, x["score"]))

print()
for lb in ["防平高危", "防平提醒", "平局观察", ""]:
    grp = [x for x in out if x["label"] == lb]
    dd = sum(1 for x in grp if x["draw"])
    print("%s: %d场 | 平局 %d (%.1f%%)" % (lb or "无预警", len(grp), dd, dd*100.0/len(grp) if grp else 0))

hi = [x for x in out if x["label"] in ("防平高危", "防平提醒")]
total_draws = sum(1 for x in out if x["draw"])
dd = sum(1 for x in hi if x["draw"])
covered = all(x["label"] in ("防平高危","防平提醒") for x in out if x["draw"])
print("\n高危+提醒合计: %d场 | 平局 %d (%.1f%%) | 20场总平局%d场, 全部覆盖: %s" % (
    len(hi), dd, dd*100.0/len(hi), total_draws, covered))
