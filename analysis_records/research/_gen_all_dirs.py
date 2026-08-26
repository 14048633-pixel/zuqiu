# -*- coding: utf-8 -*-
"""27 场全方向组明细: 每场输出 1X2 / 让球 / 大小球 三组方向表 + 每组最优 + best_bet"""
import sys, io, json, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = r"D:\足球分析\analysis_records\research"
d = json.load(io.open(os.path.join(OUT, "rerun_0822_intel.json"), encoding="utf-8"))
rows = sorted(d["matches"], key=lambda x: (x["ct"][:5], x["league"]))

def pct(o): return ("%+.1f%%" % (o*100)) if isinstance(o,(int,float)) else "-"

def pct_str(v):
    return ("%+.1f%%" % v) if isinstance(v,(int,float)) else "-"


def group_bets(bets):
    g = {"1X2": [], "让球": [], "大小球": []}
    for b in bets:
        n = b.get("name","")
        if n.startswith("1X2"): g["1X2"].append(b)
        elif n.startswith("让球"): g["让球"].append(b)
        elif n.startswith("大") or n.startswith("小"): g["大小球"].append(b)
    return g

def best_in(grp):
    pos = [b for b in grp if b.get("ev",0) > 0]
    if not pos: return None
    return max(pos, key=lambda b: b["ev"])

L = []
L.append("# 08-22 凌晨 27 场 全方向组明细（最新赔率 + BSD伤停/阵型情报）")
L.append("")
L.append("- 快照 %s｜模型完整链路 + match_package 情报注入" % d.get("pulled_at",""))
L.append("- 每组方向 = 该市场全部候选腿（1X2三项 / 让球主客 / 大小球）｜★=星级 ｜加粗=该组最优正EV ｜【BEST】=全场出单腿")
L.append("")

# ---- 总览 ----
bb_all = [x for x in rows if x["result"].get("best_bet")]
veto = [x for x in rows if x["result"].get("direction",{}).get("vetoed")]
n_pos = sum(1 for x in rows if any(b.get("ev",0)>0 for b in x["result"].get("bets") or []))
L.append("## 📊 总览")
L.append("")
L.append("| 指标 | 值 |")
L.append("|---|---|")
L.append("| 总场次 | %d |" % len(rows))
L.append("| 出单 best_bet | %d |" % len(bb_all))
L.append("| 正EV场次(任一方向) | %d |" % n_pos)
L.append("| 硬否决 | %d |" % len(veto))
L.append("")
L.append("### 按方向组统计")
L.append("")
L.append("| 方向组 | 正EV腿数 | 出单腿数 |")
L.append("|---|---|---|")
for grp in ("1X2","让球","大小球"):
    pos_n = sum(1 for x in rows for b in (x["result"].get("bets") or []) if b.get("name","").startswith(("1X2","让球","大","小")) if grp=="1X2" and b.get("name","").startswith("1X2") and b.get("ev",0)>0)
L.append("")
L.append("---")
L.append("")

# ---- 逐场 ----
for x in rows:
    r = x["result"]
    if "error" in r:
        L.append("## ❌ %s | %s vs %s：%s" % (x["league"], x["home"], x["away"], r["error"])); L.append(""); continue
    lam = r.get("lambda") or {}; wdl = r.get("wdl") or {}; mf = r.get("market_fair") or {}
    di = r.get("direction") or {}; bb2 = r.get("best_bet")
    fm = r.get("formation") or {}; rt = r.get("risk_tags") or []
    L.append("## %s | %s vs %s（%s）" % (x["league"], x["home"], x["away"], x["ct"]))
    L.append("")
    L.append("- **λ** 主 %.2f/客 %.2f（合计%.2f）｜模型1X2 主%.1f/平%.1f/客%.1f ｜市场公平 主%s/平%s/客%s" % (
        lam.get("home",0), lam.get("away",0), lam.get("sum",0),
        wdl.get("home",0), wdl.get("draw",0), wdl.get("away",0),
        mf.get("home","-"), mf.get("draw","-"), mf.get("away","-")))
    if fm.get("home") or fm.get("away"):
        L.append("- **阵型** 主%s/客%s（%s）" % (fm.get("home") or "-", fm.get("away") or "-", "当场" if fm.get("src")=="cur" else "偏好"))
    dc = r.get("dir_consistency") or {}
    if dc.get("groups"):
        gg = dc["groups"]
        L.append("- **方向组一致性** 1X2[%s %s]｜让球[%s %s]｜大小球[%s %s] → **%s**" % (
            gg.get("1X2",{}).get("dir","-"), pct_str(gg.get("1X2",{}).get("ev")),
            gg.get("让球",{}).get("dir","-"), pct_str(gg.get("让球",{}).get("ev")),
            gg.get("大小球",{}).get("dir","-"), pct_str(gg.get("大小球",{}).get("ev")),
            dc.get("level","-")))
    if rt:
        L.append("- **风险** %s" % "；".join(rt))
    L.append("")
    g = group_bets(r.get("bets") or [])
    for grp in ("1X2","让球","大小球"):
        L.append("### %s" % grp)
        L.append("")
        if not g[grp]:
            L.append("_无此市场数据_"); L.append(""); continue
        L.append("| 方向 | 模型概率 | 赔率 | EV | 星级/分层 |")
        L.append("|---|---|---|---|---|")
        bi = best_in(g[grp])
        for b in sorted(g[grp], key=lambda t: -t.get("ev",0)):
            n = b.get("name","-"); ev = b.get("ev",0)
            star_s = ("★%d[%s]" % (b.get("star",0), b.get("ev_tier","?"))) if b.get("star") else "-"
            mark = " **← 组内最优正EV**" if bi and b is bi else (" ⛔" if b.get("vetoed") else "")
            tag = "【BEST】" if bb2 and b.get("name")==bb2.get("name") else ""
            L.append("| %s%s%s | %.1f%% | %.2f | %s | %s |" % (tag, n, mark, b.get("prob",0)*100, b.get("odds",0), pct(ev), star_s))
        L.append("")
    if di.get("vetoed"):
        L.append("> ⛔ 全方向否决：%s" % (di.get("veto_reason") or "-"))
    L.append("---")
    L.append("")

out = os.path.join(OUT, "rerun_0822_all_dirs.md")
io.open(out, "w", encoding="utf-8").write("\n".join(L))
print("saved:", out, "lines:", len(L))
