# -*- coding: utf-8 -*-
"""5单组合蒙特卡洛模拟(200,000次)
输入: 每单(名称, 模型命中率, 赔率); 每轮按各自命中率独立伯努利采样, 统计组合串关/单关等额。
用法: python prediction_v2/sim_parlay5.py
"""
import numpy as np

BETS = [
    ("清水客+0.2", 0.6819, 1.775),
    ("冈山大2.5",  0.5586, 2.100),
    ("浦和主+0.5", 0.6147, 1.875),
    ("鹿岛主-0.8", 0.5668, 2.025),
    ("福冈客-0.0", 0.6438, 1.875),
]
N = 200_000
SEED = 42


def main():
    rng = np.random.default_rng(SEED)
    p = np.array([b[1] for b in BETS])
    o = np.array([b[2] for b in BETS])
    out = rng.random((N, len(BETS))) < p      # N轮 x 5单, 1=中

    parlay_odds = o.prod()
    allwin = out.all(axis=1)
    pay = np.where(allwin, parlay_odds, 0.0)  # 5串1: 全中拿连乘赔率, 否则0
    prof = pay - 1.0
    sp = (out * o).sum(axis=1)                # 单关各1注: 总回报
    sprof = sp - 5.0
    nw = out.sum(axis=1)

    print("== 5单组合模拟 N=%d seed=%d ==" % (N, SEED))
    print("组合串赔率=%.2f" % parlay_odds)
    print("全中: MC %.2f%% / 独立理论 %.2f%%" % (allwin.mean() * 100, p.prod() * 100))
    print("5串1(1注): 期望利润 +%.2f -> ROI +%.0f%%" % (prof.mean(), prof.mean() * 100))
    print("5串1赔付分位 P5/P50/P95: %.0f%%/%.0f%%/%.0f%%" % tuple(np.percentile(pay, [5, 50, 95])))
    for k in range(6):
        print("中%d场: %.2f%%" % (k, (nw == k).mean() * 100))
    print("单关各1注(共5注): 期望总利润 +%.2f -> 每注ROI +%.1f%%" % (sprof.mean(), sprof.mean() / 5 * 100))
    print("单关盈利比例(总回报>5): %.1f%%" % ((sprof > 0).mean() * 100))
    print("单关总回报分位 P5/P50/P95: %.2f/%.2f/%.2f" % tuple(np.percentile(sp, [5, 50, 95])))
    pc = p.prod() * 0.9 ** 10   # 同联赛5场相关性修正(仓库串关引擎口径)
    print("相关性修正(0.9^10): 全中 %.2f%% -> 5串1 ROI %+.1f%%" % (pc * 100, (pc * parlay_odds - 1) * 100))


if __name__ == "__main__":
    main()
