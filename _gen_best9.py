# -*- coding: utf-8 -*-
import json, io, glob, os, sys
ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2", "src"))
sys.path.insert(0, os.path.join(ROOT, "src", "models"))
sys.path.insert(0, ROOT)
from prob_calibration import dc_score_grid

p = sorted(glob.glob(r"analysis_records/scan_next24h_*.json"), key=os.path.getmtime)[-1]
d = json.load(io.open(p, encoding="utf-8"))
bests = [o for o in d if o.get("best_bet")]

def top_scores(lam, rho, n=3):
    lam_h, lam_a = lam.get("home", 0), lam.get("away", 0)
    try:
        grid = dc_score_grid(lam_h, lam_a, rho=rho, max_goals=8)
    except Exception:
        return []
    cells = []
    for i in range(9):
        for j in range(9):
            cells.append((grid[i][j], i, j))
    cells.sort(reverse=True)
    return ["%d-%d %.1f%%" % (i, j, pct * 100) for pct, i, j in cells[:n]]

L = []
L.append("# ⚽ 未来24小时 BEST %d 场完整明细（%s）" % (len(bests), os.path.basename(p).replace(".json", "")))
L.append("")
for k, o in enumerate(bests, 1):
    lam = o.get("lambda") or {}
    wdl = o.get("wdl") or {}
    mf = o.get("market_fair") or {}
    con = o.get("dir_consistency") or {}
    g = con.get("groups") or {}
    level = con.get("level", "")
    bb = o["best_bet"]
    dw = o.get("draw_warn") or {}
    rho = 0.0
    try:
        import scan_upcoming as su
        _cal = su._cal_for_league(o["league"]) or {}
        rho = _cal.get("rho", 0.0)
    except Exception:
        pass
    ts = top_scores(lam, rho)
    def gs(key):
        x = g.get(key) or {}
        if x.get("dir") is None:
            return "—"
        return "**%s** EV%+.1f%%" % (x["dir"], (x.get("ev") or 0))
    L.append("## %d. %s %s（%s）" % (k, o["ko_bjt"], o["league"], "★%d %s" % (bb.get("star", 0), bb.get("ev_tier") or "")))
    L.append("**%s vs %s**" % (o["home"], o["away"]))
    L.append("")
    L.append("| 项目 | 数值 |")
    L.append("| --- | --- |")
    L.append("| λ（主/客/合计） | %.2f / %.2f / %.2f |" % (lam.get("home", 0), lam.get("away", 0), lam.get("sum", 0)))
    L.append("| 模型 WDL | 主 %.1f%% / 平 %.1f%% / 客 %.1f%% |" % (wdl.get("home", 0), wdl.get("draw", 0), wdl.get("away", 0)))
    L.append("| 市场 WDL | 主 %.1f%% / 平 %.1f%% / 客 %.1f%% |" % (mf.get("home", 0), mf.get("draw", 0), mf.get("away", 0)))
    L.append("| 比分 Top3 | %s |" % "；".join(ts) if ts else "| 比分 Top3 | — |")
    L.append("| 方向组一致性 | 1X2[%s] 让球[%s] 大小球[%s]　→　%s |" % (gs("1X2"), gs("让球"), gs("大小球"), level))
    L.append("| BEST | **%s** p%.0f%% @%.2f　**EV%+.1f%%**　★%d（%s） |" % (bb["name"], bb["prob"] * 100, bb["odds"], bb["ev"] * 100, bb.get("star", 0), bb.get("ev_tier") or "—"))
    warn = ("⚠ 平局预警 %.0f%%（%s）" % (dw["market_draw_prob"], "强" if dw.get("strong") else "常规")) if dw else "—"
    L.append("| 平局预警 | %s |" % warn)
    risks = o.get("risk_tags") or []
    L.append("| 风险标注 | %s |" % ("；".join(risks) if risks else "—"))
    L.append("")
out_md = os.path.join(os.path.dirname(p), "best9_next24h_%s.md" % os.path.basename(p).replace(".json", "").replace("scan_next24h_", ""))
io.open(out_md, "w", encoding="utf-8").write("\n".join(L))
print("saved:", out_md)
print("\n".join(L))
