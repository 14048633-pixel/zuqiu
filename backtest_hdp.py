"""
让球盘深度回测 — 验证64%是否真实edge
=================================================
控制变量:
  1. 全场让球盘: 主队-0.5 (主队净胜>=1赢盘)
  2. 只统计"主队是热门"(oh < oa) 的比赛, 排除弱主队
  3. 分"主队热门让球" vs "客队热门受让" 对比
  4. 不同让球深度(-0.25/-0.5/-0.75/-1)的准确率
  5. 按赔率区间分析(oh 1.5-1.7/1.7-2.0/2.0-2.5)
结论: 让球盘64%是真实能力还是主场偏差
"""
import csv
import math
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

DATA_FILE = 'data/raw/combined_eu_mls.csv'


def pmf(k, lam):
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def lambda_from_odds(oh, od, oa):
    ph, pd, pa = 1/oh, 1/od, 1/oa
    total = ph + pd + pa
    ph, pd, pa = ph/total, pd/total, pa/total
    lam_h = max(0.3, -math.log(max(pa, 0.01)) * 0.8)
    lam_a = max(0.3, -math.log(max(ph, 0.01)) * 0.8)
    return lam_h, lam_a


def win_prob(lh, la, hdp):
    """主队让hdp球赢盘概率(含走水半权)"""
    full = sum(pmf(i, lh) * pmf(j, la) for i in range(8) for j in range(8) if (i - j) + hdp > 0)
    push = sum(pmf(i, lh) * pmf(j, la) for i in range(8) for j in range(8) if abs((i - j) + hdp) < 0.01)
    return full + push * 0.5


def main():
    rows = []
    with open(DATA_FILE, encoding='utf-8', errors='ignore') as f:
        for r in csv.DictReader(f):
            try:
                oh, od, oa = float(r['home_win_odds']), float(r['draw_odds']), float(r['away_win_odds'])
                if oh <= 1.0 or od <= 1.0 or oa <= 1.0:
                    continue
                rows.append({
                    'gh': int(float(r['goals_home'])), 'ga': int(float(r['goals_away'])),
                    'oh': oh, 'od': od, 'oa': oa,
                })
            except Exception:
                pass

    print(f"样本: {len(rows)} 场")
    print()

    # ========== 1. 全场: 主队-0.5 ==========
    print("【1. 让球盘(主-0.5) 总览】")
    all_c = all_t = 0
    for r in rows:
        lh, la = lambda_from_odds(r['oh'], r['od'], r['oa'])
        p = win_prob(lh, la, -0.5)
        pred = p > 0.5
        actual = r['gh'] > r['ga']
        all_c += (pred == actual)
        all_t += 1
    print(f"  全部比赛主-0.5: {all_c/all_t*100:.1f}% ({all_c}/{all_t})")

    # ========== 2. 只统计热门主队 (oh<oa) ==========
    print()
    print("【2. 热门主队让球 (oh<oa)】")
    c = t = 0
    for r in rows:
        if r['oh'] >= r['oa']: continue
        lh, la = lambda_from_odds(r['oh'], r['od'], r['oa'])
        p = win_prob(lh, la, -0.5)
        pred = p > 0.5
        actual = r['gh'] > r['ga']
        c += (pred == actual); t += 1
    print(f"  热门主队-0.5: {c/t*100:.1f}% ({c}/{t})")

    # ========== 3. 按赔率区间 ==========
    print()
    print("【3. 按主队赔率区间 (热门主队-0.5)】")
    buckets = defaultdict(lambda: [0, 0])
    for r in rows:
        if r['oh'] >= r['oa']: continue
        lh, la = lambda_from_odds(r['oh'], r['od'], r['oa'])
        p = win_prob(lh, la, -0.5)
        pred = p > 0.5
        actual = r['gh'] > r['ga']
        if r['oh'] < 1.5: key = '<1.5'
        elif r['oh'] < 1.7: key = '1.5-1.7'
        elif r['oh'] < 2.0: key = '1.7-2.0'
        elif r['oh'] < 2.5: key = '2.0-2.5'
        else: key = '>=2.5'
        buckets[key][0] += (pred == actual)
        buckets[key][1] += 1
    for k in ['<1.5', '1.5-1.7', '1.7-2.0', '2.0-2.5', '>=2.5']:
        c, t = buckets[k]
        if t: print(f"  主赔{k}: {c/t*100:.1f}% ({c}/{t})")

    # ========== 4. 不同让球深度 ==========
    print()
    print("【4. 不同让球深度 (热门主队)】")
    for hdp in [-0.25, -0.5, -0.75, -1.0, -1.25]:
        c = t = 0
        for r in rows:
            if r['oh'] >= r['oa']: continue
            lh, la = lambda_from_odds(r['oh'], r['od'], r['oa'])
            p = win_prob(lh, la, hdp)
            pred = p > 0.5
            # 结算: 主队结算 = 净胜 + hdp (hdp负=主队让)
            net = (r['gh'] - r['ga']) + hdp
            actual_win = net > 0
            c += (pred == actual_win); t += 1
        print(f"  主{hdp}: {c/t*100:.1f}% ({c}/{t})")

    # ========== 5. 随机基准 ==========
    print()
    print("【5. 基准对照】")
    # 主队胜率(实际)
    home_win_rate = sum(1 for r in rows if r['gh'] > r['ga']) / len(rows)
    print(f"  实际主队胜率: {home_win_rate*100:.1f}%")
    print(f"  (如果模型只预测'主队赢', 准确率 = 主队胜率)")


if __name__ == '__main__':
    main()
