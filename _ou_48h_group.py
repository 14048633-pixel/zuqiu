# -*- coding: utf-8 -*-
import io, json, re, unicodedata

ROOT = r"D:\足球分析"
def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return "".join(c for c in s if c.isalnum())

# 1) 结算表解析
md = io.open(ROOT + r"\analysis_records\settle_48h_20260818.md", encoding="utf-8").read()
settle = []
for line in md.splitlines():
    if not line.startswith("| 08-"): continue
    cells = [c.strip() for c in line.strip("|").split("|")]
    if len(cells) < 12: continue
    # 0开赛 1联赛 2比赛 3比分 4状态 5方向1x2 6命中 7大小球 8大小命中 9模型腿 10模型 11星级
    m = re.match(r"(.+?)\s+vs\s+(.+)", cells[2])
    if not m: continue
    ou_dir = re.sub(r"\s*[0-9.]+%", "", cells[7]).strip()
    ou_hit = cells[8].strip()
    settle.append({"ko": cells[0], "league": cells[1], "home": m.group(1), "away": m.group(2),
                   "score": cells[3], "ou_dir": ou_dir, "ou_hit": ou_hit})
print("结算场次:", len(settle))

# 2) 48h 计划 (模型方向 + 市场盘口)
plan = json.load(io.open(ROOT + r"\analysis_records\48h_plan_20260817.json", encoding="utf-8"))["rows"]
pmap = {}
for r in plan:
    pmap[norm(r["home"]) + "|" + norm(r["away"])] = r

def mkt_dir_from_totals(t):
    ov, un = t.get("over"), t.get("under")
    if not ov or not un: return None
    po = (1.0/ov) / (1.0/ov + 1.0/un)
    return ("大2.5" if po > 0.5 else "小2.5", po*100)

rows = []
for s in settle:
    key = norm(s["home"]) + "|" + norm(s["away"])
    p = pmap.get(key)
    if p is None:
        # 反向匹配
        key2 = norm(s["away"]) + "|" + norm(s["home"])
        p = pmap.get(key2)
    model_ou = None
    if p:
        m = re.match(r"(大|小)2?\.?5?", p.get("ou", ""))
        model_ou = m.group(0).replace("2", "2.") if m else p.get("ou","").split()[0]
    mkt = mkt_dir_from_totals((p or {}).get("totals") or {}) if p else None
    hit = (s["ou_hit"] == "✔")
    if model_ou and mkt:
        same = (model_ou[0] == mkt[0][0])
    else:
        same = None
    rows.append({
        "ko": s["ko"], "league": s["league"], "match": s["home"]+" vs "+s["away"],
        "score": s["score"], "model": model_ou or "—", "mkt": (mkt[0] if mkt else "—"),
        "mkt_p": (round(mkt[1],0) if mkt else None), "hit": hit, "same": same, "dir": s["ou_dir"],
    })

same = [r for r in rows if r["same"] is True]
opp  = [r for r in rows if r["same"] is False]
no   = [r for r in rows if r["same"] is None]
def stat(rs):
    if not rs: return "n=0"
    hit = sum(1 for r in rs if r["hit"])
    return "n=%d 命中%d (%.1f%%)" % (len(rs), hit, 100.0*hit/len(rs))
print()
print("== 模型 vs 市场(BSD/totals) 方向分组 ==")
print("同向:", stat(same))
print("反向:", stat(opp))
print("无市场方向:", stat(no))
print()
print("| 时间 | 联赛 | 对阵 | 比分 | 模型 | 市场 | 市场大球% | 命中 | 分组 |")
for r in sorted(rows, key=lambda x: x["ko"]):
    g = "同向" if r["same"] is True else ("反向" if r["same"] is False else "—")
    m = ("%.0f%%" % r["mkt_p"]) if r["mkt_p"] is not None else "—"
    print("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
        r["ko"], r["league"], r["match"], r["score"], r["model"], r["mkt"], m, "✔" if r["hit"] else "✘", g))
