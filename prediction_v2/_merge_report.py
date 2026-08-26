# -*- coding: utf-8 -*-
"""合并扫描方向 + 完整信息 -> 逐场报告 (scan_report_YYYYMMDD.md)
输入: analysis_records/20260816_scan_upcoming.json (含 direction + info)
      analysis_records/matches_info_20260816.json (完整信息兜底)
输出: analysis_records/scan_report_20260816.md
"""
import io, json, os, sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BJT = timezone(timedelta(hours=8))
SCAN = os.path.join(ROOT, "analysis_records", "20260816_scan_upcoming.json")
INFO = os.path.join(ROOT, "analysis_records", "matches_info_20260816.json")
OUT = os.path.join(ROOT, "analysis_records", "scan_report_20260816.md")

def main():
    sys.stdout.reconfigure(encoding="utf-8")
    scan = json.load(io.open(SCAN, encoding="utf-8"))
    try:
        info_map = {(m["league"], m["home"], m["away"]): m
                    for m in json.load(io.open(INFO, encoding="utf-8")).get("matches", [])}
    except Exception:
        info_map = {}
    now = datetime.now(timezone.utc)
    lines = ["# 扫描报告: 方向 + 完整信息 (%s)" % datetime.now(BJT).strftime("%Y-%m-%d %H:%M"),
             "", "未开赛场次逐场列出; 否决场次方向仍给出并标注原因。", ""]
    day = ""
    n_bet = 0
    n_show = 0
    for m in sorted(scan["matches"], key=lambda x: x["ct"]):
        ct = datetime.fromisoformat(m["ct"]).replace(tzinfo=timezone.utc)
        if ct <= now:
            continue
        r = m["result"]
        bj = ct.astimezone(BJT)
        d0 = bj.strftime("%m-%d")
        if d0 != day:
            day = d0
            lines.append("## %s" % d0)
        di = r.get("direction")
        bb = r.get("best_bet")
        lines.append("### %s %s  %s vs %s" % (bj.strftime("%H:%M"), m["league"], m["home"], m["away"]))
        lines.append("- λ: %.2f / %.2f | 数据源: %s/%s | 快照距开赛: %s h" % (
            r["lambda"]["home"], r["lambda"]["away"], r["data_src"]["home"],
            r["data_src"]["away"], r.get("snap_age_h")))
        if di:
            mk = ("市场%.0f%%" % (di["market_fair"] * 100)) if di.get("market_fair") is not None else "市场-"
            v = (" ⛔否决: %s" % di["veto_reason"]) if di.get("vetoed") else ""
            wmk = ("市场%.0f%%" % (di["wdl_market_fair"] * 100)) if di.get("wdl_market_fair") is not None else "市场-"
            lines.append("- 方向: **%s %.0f%% @%.2f (%s)**%s | 胜平负: %s %.0f%% (%s)" % (
                di["name"], di["prob"] * 100, di["odds"], mk, v, di["wdl_name"],
                di["wdl_prob"] * 100, wmk))
        else:
            lines.append("- 方向: 无盘口")
        if bb:
            n_bet += 1
            lines.append("- best_bet: **%s %.0f%% @%.2f EV%+.1f%% ★%d [%s]**" % (
                bb["name"], bb["prob"] * 100, bb["odds"], bb["ev"] * 100,
                bb.get("star", 0), bb.get("ev_tier", "?")))
        if r.get("risk_tags"):
            lines.append("- 风险: %s" % ", ".join(r["risk_tags"]))
        inf = r.get("info") or info_map.get((m["league"], m["home"], m["away"]))
        if inf:
            n_show += 1
            for side, tag in (("home", "主"), ("away", "客")):
                it = inf.get(side + "_info")
                es = inf.get(side + "_espn")
                if not it or not es:
                    lines.append("- %s队 %s: 无ESPN数据(数据源未覆盖)" % (tag, inf.get(side)))
                    continue
                src = ("跨联赛:%s" % inf.get(side + "_src_lg")) if inf.get(side + "_src_lg") != m["league"] else "同联赛"
                rk = ("第%d名" % it["rank"]) if it.get("rank") else "未进本季榜"
                f5 = "; ".join(it.get("form5") or []) or "无"
                fh = "; ".join(it.get("form5_home" if side == "home" else "form5_away") or []) or "无"
                lines.append("- %s队 %s [%s %s]: 本季 %d场 %d胜%d平%d负 进%d失%d 积%d %s" % (
                    tag, inf.get(side), es, src, it["P"], it["W"], it["D"], it["L"],
                    it["GF"], it["GA"], it["Pts"], rk))
                lines.append("  - 近5: %s" % f5)
                lines.append("  - 近5%s: %s" % ("主" if side == "home" else "客", fh))
            lines.append("- 交锋: %s" % ("; ".join(inf.get("h2h") or []) or "无记录"))
            lines.append("- 情报: %s" % inf.get("intel", "未获取"))
        else:
            lines.append("- 完整信息: 未生成(非未开赛场次)")
        lines.append("")
    lines.append("---")
    lines.append("未开赛场次: %d | 附完整信息: %d | 可出best_bet: %d" % (n_show and 0 or 0, n_show, n_bet))
    # 修正统计: 重新数
    del lines[-1]
    unsettled = [m for m in scan["matches"] if datetime.fromisoformat(m["ct"]).replace(tzinfo=timezone.utc) > now]
    lines.append("未开赛场次: %d | 附完整信息: %d | 可出best_bet: %d" % (len(unsettled), n_show, n_bet))
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("已生成 %s (%d 场未开赛, %d 场带完整信息, %d 场可出单)" % (OUT, len(unsettled), n_show, n_bet))

if __name__ == "__main__":
    main()
