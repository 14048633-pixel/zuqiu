# -*- coding: utf-8 -*-
"""阶段复盘工具: 以 N 场(默认300)为一个阶段, 从实盘台账生成复盘报告
用法:
  python phase_review.py                 # 默认阶段目标300
  python phase_review.py --phase 100     # 阶段目标100
  python phase_review.py --min-n 5       # 结论最小样本数(默认5)
输出:
  analysis_records/phase_reports/phase_YYYYMMDD.md   阶段复盘报告
  analysis_records/phase_hypotheses.md               观察规则库(跨阶段累积)
"""
import argparse, csv, io, json, os, sys
from collections import defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(ROOT, "analysis_records", "bet_ledger.csv")
REPORT_DIR = os.path.join(ROOT, "analysis_records", "phase_reports")
HYP = os.path.join(ROOT, "analysis_records", "phase_hypotheses.md")

PHASE_DEFAULT = 300
MIN_N_DEFAULT = 5


def _f(x):
    try:
        return float(x)
    except Exception:
        return 0.0


def load_rows():
    rows = []
    if os.path.exists(LEDGER):
        with io.open(LEDGER, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(r)
    return rows


def settled(rows):
    return [r for r in rows if r.get("status") == "已结算"]


def result_cls(r):
    return (r.get("result") or "").strip().lower()


def roi(r):
    return _f(r.get("pnl") or 0)


def weighted_roi(r):
    return _f(r.get("stake_factor") or 0) * _f(r.get("pnl") or 0)


def group_stats(items, keyfn, min_n=MIN_N_DEFAULT):
    g = defaultdict(list)
    for r in items:
        g[keyfn(r)].append(r)
    out = []
    for k, v in sorted(g.items(), key=lambda kv: -len(kv[1])):
        n = len(v)
        wins = sum(1 for r in v if result_cls(r) == "win")
        halves = sum(1 for r in v if result_cls(r) == "half")
        pnl = sum(roi(r) for r in v)
        wroi = sum(weighted_roi(r) for r in v)
        stake = sum(_f(r.get("stake_factor") or 0) for r in v)
        wroi_pct = 100 * wroi / stake if stake else 0.0
        wr_pct = 100 * (wins + 0.5 * halves) / n if n else 0.0
        out.append({
            "k": k, "n": n, "wins": wins, "halves": halves, "losses": n - wins - halves,
            "roi_pct": 100 * pnl / n if n else 0.0, "wroi_pct": wroi_pct,
            "wr_pct": wr_pct, "enough": n >= min_n,
        })
    return out


def bet_type(r):
    n = r.get("bet_name") or ""
    if n.startswith("让球"):
        m = __import__("re").match(r"让球(主|客)\(([+-][\d.]+)\)", n)
        line = m.group(2) if m else "?"
        return "让球" + m.group(1) + line
    if n.startswith("大"):
        return "大球"
    if n.startswith("小"):
        return "小球"
    if n.startswith("1X2"):
        return "1X2"
    return n[:6]


def risk_present(tag):
    def fn(r):
        return "Y" if tag in (r.get("risk_tags") or "") else "N"
    return fn


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", type=int, default=PHASE_DEFAULT)
    ap.add_argument("--min-n", type=int, default=MIN_N_DEFAULT)
    args = ap.parse_args()

    rows = load_rows()
    done = settled(rows)
    os.makedirs(REPORT_DIR, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    fname = "phase_%s.md" % datetime.now().strftime("%Y%m%d")
    path = os.path.join(REPORT_DIR, fname)

    lines = []
    A = lines.append
    A("# 阶段复盘报告")
    A("")
    A("- 生成时间: %s" % now)
    A("- 阶段目标: %d 场 | 台账累计: %d | 待结算: %d | 已结算: %d | 还差: %d" % (
        args.phase, len(rows), len(rows) - len(done), len(done), max(0, args.phase - len(rows))))
    A("")
    wins = sum(1 for r in done if result_cls(r) == "win")
    halves = sum(1 for r in done if result_cls(r) == "half")
    pnl = sum(roi(r) for r in done)
    wstake = sum(_f(r.get("stake_factor") or 0) for r in done)
    wroi = sum(weighted_roi(r) for r in done)
    A("## 总览")
    A("")
    A("| 指标 | 值 |")
    A("|---|---|")
    A("| 已结算 | %d |" % len(done))
    A("| 胜/半/负 | %d / %d / %d |" % (wins, halves, len(done) - wins - halves))
    A("| 简单胜率 | %.1f%% |" % (100 * wins / len(done) if done else 0))
    A("| 含半胜率 | %.1f%% |" % (100 * (wins + 0.5 * halves) / len(done) if done else 0))
    A("| 单注ROI(每注1单位) | %+.1f%% |" % (100 * pnl / len(done) if done else 0))
    A("| 权重ROI(按仓位) | %+.1f%% |" % (100 * wroi / wstake if wstake else 0))
    A("")

    def section(title, gs, unit=""):
        A("## %s" % title)
        A("")
        A("| 分组 | n | 胜 | 半 | 负 | 胜率(含半) | 单注ROI | 权重ROI | 结论 |")
        A("|---|---|---|---|---|---|---|---|---|")
        for s in gs:
            if s["enough"]:
                tag = ""
                if s["wroi_pct"] >= 15:
                    tag = "🟢正向"
                elif s["wroi_pct"] <= -15:
                    tag = "🔴负向"
                else:
                    tag = "⚪中性"
            else:
                tag = "样本不足"
            A("| %s | %d | %d | %d | %d | %.1f%% | %+.1f%% | %+.1f%% | %s |" % (
                s["k"], s["n"], s["wins"], s["halves"], s["losses"], s["wr_pct"], s["roi_pct"], s["wroi_pct"], tag))
        A("")

    section("按联赛", group_stats(done, lambda r: r.get("league") or "?", args.min_n))
    section("按注单类型", group_stats(done, bet_type, args.min_n))
    section("按星级", group_stats(done, lambda r: "★%s" % (r.get("star") or "?"), args.min_n))
    section("按EV分层", group_stats(done, lambda r: r.get("ev_tier") or "?", args.min_n))
    section("按否决状态", group_stats(done, lambda r: "否决单" if _f(r.get("veto") or 0) else "正常单", args.min_n))
    section("带'队名模糊匹配'标签", group_stats(done, risk_present("队名模糊匹配"), args.min_n))
    section("带'纯数据无伤病情报'标签", group_stats(done, risk_present("纯数据无伤病情报"), args.min_n))

    # 成交价滑点(有 placed_odds 时)
    slip = [r for r in done if r.get("placed_odds") and r.get("odds")]
    if slip:
        diffs = [(_f(r["placed_odds"]) / _f(r["odds"]) - 1) * 100 for r in slip if _f(r["odds"]) > 0]
        if diffs:
            A("## 成交价滑点")
            A("")
            A("| 项目 | 值 |")
            A("|---|---|")
            A("| 有成交价记录 | %d/%d |" % (len(slip), len(done)))
            A("| 平均滑点 | %+.1f%% |" % (sum(diffs) / len(diffs)))
            A("")

    # 结论汇总 (仅样本充足)
    A("## 有效结论(样本>=%d)" % args.min_n)
    A("")
    found = False
    for title, gs in [
        ("联赛", group_stats(done, lambda r: r.get("league") or "?", args.min_n)),
        ("注单类型", group_stats(done, bet_type, args.min_n)),
        ("EV分层", group_stats(done, lambda r: r.get("ev_tier") or "?", args.min_n)),
        ("否决状态", group_stats(done, lambda r: "否决单" if _f(r.get("veto") or 0) else "正常单", args.min_n)),
    ]:
        for s in gs:
            if s["enough"] and abs(s["wroi_pct"]) >= 15:
                A("- [%s] %s: n=%d, 权重ROI %+.1f%% %s" % (
                    title, s["k"], s["n"], s["wroi_pct"], "🟢" if s["wroi_pct"] > 0 else "🔴"))
                found = True
    if not found:
        A("- 暂无样本充足的显著方向(继续积累)")
    A("")
    A("## 观察规则(待验证, 不直接改系统)")
    A("")
    A("> 样本<30 前只做观察; 连续两阶段同向且 n>=30 才升级为系统规则。")
    A("")
    with io.open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("报告已生成: %s" % path)
    print("已结算 %d/%d | 权重ROI %+.1f%%" % (len(done), args.phase, 100 * wroi / wstake if wstake else 0))


if __name__ == "__main__":
    main()
