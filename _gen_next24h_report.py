# -*- coding: utf-8 -*-
import json, io, glob, os
p = sorted(glob.glob(r"analysis_records/scan_next24h_*.json"), key=os.path.getmtime)[-1]
d = json.load(io.open(p, encoding="utf-8"))
L = []
L.append("⚽ 未来24小时扫描报告（%s）" % os.path.basename(p))
L.append("总场次=%d | best_bet=%d | 被否决=%d" % (
    len(d), sum(1 for o in d if o["best_bet"]), sum(1 for o in d if o["vetoed"])))
L.append("")
for o in d:
    lam = o.get("lambda") or {}
    wdl = o.get("wdl") or {}
    mf = o.get("market_fair") or {}
    con = o.get("dir_consistency") or {}
    g = con.get("groups") or {}
    level = con.get("level", "")
    def gs(key):
        x = g.get(key) or {}
        if x.get("dir") is None:
            return "-"
        return "%s %+.1f%%" % (x["dir"], (x.get("ev") or 0))
    dw = o.get("draw_warn") or {}
    dws = "⚠平局%.0f%%" % dw["market_draw_prob"] if dw else ""
    veto = "⛔否决:%s" % o["veto_reason"] if o["vetoed"] else ""
    bb = o["best_bet"]
    bbs = "%s p%.0f%% @%.2f EV%+.1f%% ★%d%s" % (bb["name"], bb["prob"]*100, bb["odds"], bb["ev"]*100, bb.get("star", 0), "(" + str(bb.get("ev_tier")) + ")") if bb else "无"
    risks = ";".join(o.get("risk_tags") or [])
    L.append("【%s %s】%s vs %s" % (o["ko_bjt"], o["league"], o["home"], o["away"]))
    L.append("  λ 主%.2f/客%.2f | 模型WDL %s/%s/%s | 市场WDL %s/%s/%s" % (
        lam.get("home", 0), lam.get("away", 0),
        wdl.get("home", ""), wdl.get("draw", ""), wdl.get("away", ""),
        mf.get("home", ""), mf.get("draw", ""), mf.get("away", "")))
    L.append("  方向组: 1X2[%s] 让球[%s] 大小球[%s] | %s" % (gs("1X2"), gs("让球"), gs("大小球"), level))
    L.append("  BEST: %s" % bbs)
    if dws or veto or risks:
        L.append("  标注: %s %s %s" % (dws, veto, risks))
    L.append("")
out_md = os.path.join(os.path.dirname(p), os.path.basename(p).replace(".json", ".md"))
io.open(out_md, "w", encoding="utf-8").write("\n".join(L))
print("saved", out_md)
print("\n".join(L))
