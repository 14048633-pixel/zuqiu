# -*- coding: utf-8 -*-
"""回测: 方向组一致性=三向一致 的历史实盘命中率
样本: 08-22 分析(0141/2136) + 08-23 窗口分析 + 43场 -> 关联 settle 比分判断 1X2/让球/大小球 三向各自命中与全中
"""
import io, json, glob, re
from collections import Counter

def load(fn):
    try:
        return json.load(io.open(fn, encoding="utf-8"))
    except Exception:
        return None

# 1) 历史分析: 取每批最新一份
ana_files = ["analysis_records/scan24h_analysis_20260822_0141.json",
             "analysis_records/scan24h_analysis_20260822_2136.json",
             "analysis_records/scan24h_analysis_20260823_1824.json"]
matches = {}
for fn in ana_files:
    d = load(fn)
    if not d:
        continue
    for m in (d.get("matches") or []):
        dc = m.get("dir_consistency")
        if not dc:
            continue
        key = (m.get("league"), m.get("home"), m.get("away"))
        matches.setdefault(key, m)
# 43场也并入
d43 = load("analysis_records/pending_43_20260823.json")
for m in (d43 or {}).get("matches") or []:
    dc = m.get("dir_consistency")
    if dc:
        key = (m.get("league"), m.get("home"), m.get("away"))
        matches.setdefault(key, m)

# 2) settle 比分库
scores = {}
for fn in glob.glob("analysis_records/scan24h_settle_*.json") + glob.glob("analysis_records/scan48h_settle_*.json"):
    d = load(fn)
    if not d:
        continue
    for s in (d.get("settled") or []):
        if not isinstance(s, dict):
            continue
        key = (s.get("league"), s.get("home"), s.get("away"))
        if s.get("score") or s.get("hg") is not None:
            scores.setdefault(key, s)

def parse_hdp(name):
    m = re.search(r"[+-]\d+(?:\.\d+)?", name or "")
    return float(m.group(0)) if m else 0.0

def judge(hg, ag, dir1x2, dir_hdp, dir_ou):
    out = {}
    if "主胜" in (dir1x2 or ""):
        out["1X2"] = "win" if hg > ag else ("push" if hg == ag else "lose")
    elif "客胜" in (dir1x2 or ""):
        out["1X2"] = "win" if ag > hg else ("push" if hg == ag else "lose")
    elif "平局" in (dir1x2 or ""):
        out["1X2"] = "win" if hg == ag else "lose"
    else:
        out["1X2"] = None
    if dir_hdp:
        side = "主" if "主" in dir_hdp else "客"
        hdp = parse_hdp(dir_hdp)
        diff = (hg - ag) if side == "主" else (ag - hg)
        v = diff + hdp
        out["让球"] = "win" if v > 0.001 else ("lose" if v < -0.001 else "push")
    else:
        out["让球"] = None
    if dir_ou:
        mm = re.match(r"^(大|小)(\d+(?:\.\d+)?)", dir_ou)
        if mm:
            side, line = mm.group(1), float(mm.group(2))
            total = hg + ag
            if abs(total - line) < 0.001:
                out["大小球"] = "push"
            elif (side == "大" and total > line) or (side == "小" and total < line):
                out["大小球"] = "win"
            else:
                out["大小球"] = "lose"
        else:
            out["大小球"] = None
    else:
        out["大小球"] = None
    return out

rows = []
for key, m in matches.items():
    dc = m.get("dir_consistency") or {}
    if dc.get("level") != "三向一致":
        continue
    g = dc.get("groups") or {}
    d1 = (g.get("1X2") or {}).get("dir")
    dh = (g.get("让球") or {}).get("dir")
    do = (g.get("大小球") or {}).get("dir")
    s = scores.get(key) or {}
    hg, ag = s.get("hg"), s.get("ag")
    if hg is None or ag is None:
        rows.append({"key": key, "score": s.get("score"), "status": "无比分", "j": None})
        continue
    j = judge(hg, ag, d1, dh, do)
    rows.append({"key": key, "score": "%d-%d" % (hg, ag), "dirs": (d1, dh, do), "j": j, "status": "ok"})

print("三向一致总场次(含无比分):", len(rows))
ok = [r for r in rows if r["status"] == "ok"]
print("有比分场次:", len(ok))
for side in ("1X2", "让球", "大小球"):
    c = Counter(r["j"].get(side) for r in ok if r["j"])
    w = c.get("win", 0)
    print("  %s 方向命中: %d/%d = %.1f%% (win/lose/push=%s)" % (side, w, len(ok), w / len(ok) * 100, dict(c)))
full = [r for r in ok if r["j"] and all(r["j"].get(s) in ("win", "push") for s in ("1X2", "让球", "大小球"))]
allwin = [r for r in ok if r["j"] and all(r["j"].get(s) == "win" for s in ("1X2", "让球", "大小球"))]
print("三向全中(含走水): %d/%d" % (len(full), len(ok)))
print("三向全中(全赢): %d/%d = %.1f%%" % (len(allwin), len(ok), len(allwin) / len(ok) * 100 if ok else 0))
print()
for r in ok:
    print("%-10s %-24s vs %-24s | 比分%s | 1X2=%s 让球=%s 大小球=%s" % (
        r["key"][0], r["key"][1], r["key"][2], r["score"],
        r["j"].get("1X2"), r["j"].get("让球"), r["j"].get("大小球")))
