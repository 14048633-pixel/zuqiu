# -*- coding: utf-8 -*-
import json, io, sys, unicodedata, collections
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\足球分析\prediction_v2")
from draw_warning import draw_warning_score, draw_warning_label

ROOT = r"D:\足球分析"
def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return "".join(c for c in s if c.isalnum())

# ---- 索引扫描快照回填平局赔率 ----
idx = {}
for f in ("20260815_scan_upcoming.json", "20260816_scan_upcoming.json"):
    d = json.load(io.open(ROOT + r"\analysis_records\\" + f, encoding="utf-8"))
    for m in d.get("matches", []):
        r = m.get("result") or {}
        bets = r.get("bets") or []
        dp = None; hp = None; ap = None
        for b in bets:
            n = (b.get("name") or "").replace(" ", "")
            if "1X2" in n:
                if "平" in n: dp = b.get("odds")
                elif "主胜" in n: hp = b.get("odds")
                elif "客胜" in n: ap = b.get("odds")
        key = (m.get("league"), norm(m.get("home")), norm(m.get("away")))
        v = {"dp": dp, "hp": hp, "ap": ap}
        idx[key] = v
        idx[(m.get("league"), norm(m.get("away")), norm(m.get("home")))] = v

# ---- 账本 78 场 ----
led = json.load(io.open(ROOT + r"\_matched_full.json", encoding="utf-8"))
rows = []
miss = 0
for r in led:
    k = (r["league"], norm(r["home"]), norm(r["away"]))
    v = idx.get(k)
    if not v or not v["dp"]:
        miss += 1
        continue
    info = {
        "league": r["league"],
        "h2h": [v["hp"], v["dp"], v["ap"]],
        "resonance": "硬否决" if str(r.get("veto")) == "1" else "共振",
        "model_leg": r.get("bet_name") or "",
        "form": "中性",
    }
    sc, tags = draw_warning_score(info)
    rows.append({"sc": sc, "label": draw_warning_label(sc), "tags": tags,
                 "is_draw": bool(r.get("is_draw")), "match": r["match"],
                 "league": r["league"], "bet": r.get("bet_name"),
                 "veto": r.get("veto"), "dp": v["dp"]})

print("== 账本 78 场 v2 验证 (回填平赔 %d/78) ==" % (78 - miss))
tot = len(rows)
draws = sum(1 for x in rows if x["is_draw"])
print("总场次 %d | 平局 %d (%.1f%%)" % (tot, draws, draws * 100.0 / tot))
print("\n-- 按分值分档 --")
buckets = [(0, "0分"), (1, "1分"), (2, "2分"), (3, "3分"), (4, "4分"), (5, "5分+")]
for lo, name in buckets:
    grp = [x for x in rows if (lo <= x["sc"] < lo + 1) if lo < 5] if lo < 5 else [x for x in rows if x["sc"] >= 5]
    if lo < 5:
        grp = [x for x in rows if x["sc"] == lo]
    if not grp:
        print("%s: 0 场" % name); continue
    dd = sum(1 for x in grp if x["is_draw"])
    print("%s: %d 场 | 平局 %d (%.1f%%)" % (name, len(grp), dd, dd * 100.0 / len(grp)))

print("\n-- 按标签分档 --")
for lb in ["防平高危", "防平提醒", "平局观察", ""]:
    grp = [x for x in rows if x["label"] == lb]
    if not grp:
        print("%s: 0 场" % (lb or "无预警")); continue
    dd = sum(1 for x in grp if x["is_draw"])
    print("%s: %d 场 | 平局 %d (%.1f%%)" % (lb or "无预警", len(grp), dd, dd * 100.0 / len(grp)))

print("\n-- 防平高危明细 --")
for x in [x for x in rows if x["label"] == "防平高危"]:
    print("  %s | %s | 平赔%.2f | %s" % ("平局" if x["is_draw"] else "非平", x["match"], x["dp"], "/".join(x["tags"])))
