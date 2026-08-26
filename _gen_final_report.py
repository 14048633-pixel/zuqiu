# -*- coding: utf-8 -*-
import json, io, sys, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r"D:\足球分析"
scan = json.load(open(os.path.join(ROOT, "analysis_records", "scan_next24h_20260825_0021.json"), encoding="utf-8"))
res = json.load(open(os.path.join(ROOT, "analysis_records", "results_all_20260825.json"), encoding="utf-8"))
resmap = {(r['home'], r['away']): r for r in res}
scanmap = {}
for m in scan:
    scanmap[(m['home'], m['away'])] = m

def parse_total_line(name):
    mm = re.match(r'^([大小])(\d+\.?\d*)$', name or '')
    if mm:
        return mm.group(1), float(mm.group(2))
    return None

def parse_ah(name):
    mm = re.match(r'^让球(主|客)\(([+-]\d+\.?\d*)\)$', name or '')
    if mm:
        return mm.group(1), float(mm.group(2))
    return None

def judge_leg(name, hs, as_, draw_prob=None):
    """返回 (结果, 说明) 结果: 赢/输/走水/半赢/半输"""
    ov = parse_total_line(name)
    if ov:
        side, line = ov
        total = hs + as_
        if side == '大':
            return ('赢' if total > line else '走水' if total == line else '输'), f"总{total}"
        else:
            return ('赢' if total < line else '走水' if total == line else '输'), f"总{total}"
    ah = parse_ah(name)
    if ah:
        side, line = ah
        gh = line if side == '主' else -line   # 主队带符号让球值: 让球主(+X)=主受让X, 让球客(+X)=客受让X(主让X)
        ga = -gh
        adj_h, adj_a = hs + gh, as_ + ga
        diff = adj_h - adj_a
        if diff == 0:
            if abs(line) == 0.25:
                # 平局 + 四分之一盘: 受让方半赢
                return ('半赢' if line > 0 else '半输'), f"让球后平 {adj_h:.2f}-{adj_a:.2f}"
            return '走水', f"让球后 {adj_h:.2f}-{adj_a:.2f}"
        win = (diff > 0) if side == '主' else (diff < 0)   # diff>0 主赢盘; 方向让X看X是否赢盘
        return ('赢' if win else '输'), f"让球后 {adj_h:.2f}-{adj_a:.2f}"
    if name.startswith('1X2'):
        side = name.replace('1X2','').strip()
        if side == '主胜': want='home'
        elif side == '客胜': want='away'
        else: want='draw'
        if want=='home': return ('赢' if hs>as_ else '输'), f"{hs}-{as_}"
        if want=='away': return ('赢' if as_>hs else '输'), f"{hs}-{as_}"
        return ('赢' if hs==as_ else '输'), f"{hs}-{as_}"
    return '?', ''

lines = []
lines.append("# 2026-08-25 扫描 34 场最终分析报告")
lines.append("")
lines.append("- 扫描文件: `scan_next24h_20260825_0021.json` | 结果合并: `results_all_20260825.json`")
lines.append("- 结果来源: BSD 21 场 + API-Football 13 场(双源交叉验证) | Hallescher 比分以 API-Football 为准(BSD 误报已修正)")
lines.append("")

best_rows = []
dir_rows = []
veto_rows = []
for r in res:
    h, a = r['home'], r['away']
    m = scanmap.get((h,a)) or {}
    lam = m.get('lambda') or {}
    wdl = m.get('wdl') or {}
    mf = m.get('market_fair') or {}
    dc = m.get('dir_consistency') or {}
    hs, as_ = None, None
    if r.get('score'):
        p = r['score'].split('-')
        hs, as_ = int(p[0]), int(p[1])
    block = []
    best = r.get('best_bet')
    veto = r.get('vetoed')
    block.append(f"### {r['ko_bjt']} {r['league']} | {h} vs {a} | **{r['score']}**")
    block.append(f"- λ: 主{lam.get('home')} / 客{lam.get('away')} | 模型WDL {wdl.get('home')}/{wdl.get('draw')}/{wdl.get('away')} | 市场 {mf.get('home')}/{mf.get('draw')}/{mf.get('away')}")
    dl = m.get('direction') or '无'
    dev = (m.get('dir_ev') or 0)*100
    block.append(f"- 方向: **{dl}** p{m.get('dir_prob')} 赔{m.get('dir_odds')} EV{dev:+.1f}% ★{m.get('star')} | 一致性: {dc.get('level')}")
    tags = m.get('risk_tags') or []
    if tags:
        block.append(f"- 风险: {'; '.join(tags)}")
    if best:
        bev = (r.get('bb_ev') or 0)*100
        if hs is not None:
            jr, why = judge_leg(best, hs, as_)
            block.append(f"- BEST: **{best}** EV{bev:+.1f}% → **{jr}** ({why})")
            best_rows.append((r['ko_bjt'], r['league'], h, a, best, r['score'], jr, r.get('vetoed')))
        else:
            block.append(f"- BEST: {best} EV{bev:+.1f}% (无比分)")
    if veto:
        block.append(f"- ⚠️ **否决**: {r.get('veto_reason')}")
    if hs is not None and not veto:
        jr, why = judge_leg(dl, hs, as_)
        block.append(f"- 方向判定: **{jr}** ({why})")
        dir_rows.append((r['ko_bjt'], r['league'], h, a, dl, r['score'], jr))
    elif veto and hs is not None:
        jr, why = judge_leg(dl, hs, as_)
        block.append(f"- (否决场方向若打: {jr})")
    lines.extend(block)
    lines.append("")

# 汇总
def stat(rows):
    from collections import Counter
    c = Counter(x[6] for x in rows)
    return c

best_stat = stat(best_rows)
dir_stat = stat(dir_rows)
lines.append("---")
lines.append("## 汇总统计")
lines.append(f"- BEST 出单 {len(best_rows)} 场: {dict(best_stat)}")
lines.append(f"- 非否决方向参考 {len(dir_rows)} 场: {dict(dir_stat)}")
lines.append("")

from collections import Counter
lc = Counter()
for r in res:
    lc[r['league']] += 1
lines.append("## 联赛分布")
for k, v in lc.most_common():
    lines.append(f"- {k}: {v} 场")
lines.append("")
txt = "\n".join(lines)
out = os.path.join(ROOT, "analysis_records", "final_report_20260825_34.md")
io.open(out, 'w', encoding='utf-8').write(txt)
print("saved", out)
print()
print("BEST 统计:", dict(best_stat), "总数", len(best_rows))
print("方向统计:", dict(dir_stat), "总数", len(dir_rows))
print()
for x in best_rows:
    print("BEST", x)
