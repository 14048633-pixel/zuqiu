# -*- coding: utf-8 -*-
"""单场比分蒙特卡洛模拟: 独立泊松(lambda_home, lambda_away), 20万次/场, 求众数比分+前5比分"""
import numpy as np

MATCHES = [
    ("水户蜀葵 vs 大阪钢巴", 1.13, 1.50, None),
    ("清水鼓动 vs 横滨水手", 1.23, 1.43, "清水客+0.2 @1.775"),
    ("冈山绿雉 vs 长崎航海", 1.57, 1.35, "冈山大2.5 @2.10"),
    ("浦和红钻 vs 广岛三箭", 1.20, 1.31, "浦和主+0.5 @1.875"),
    ("千叶市原 vs 町田泽维亚", 0.94, 1.62, None),
    ("川崎前锋 vs 京都不死鸟", 1.44, 1.17, None),
    ("神户胜利船 vs FC东京", 1.06, 1.42, None),
    ("鹿岛鹿角 vs 名古屋鲸", 1.72, 0.88, "鹿岛主-0.8 @2.025"),
    ("福冈黄蜂 vs 大阪樱花", 0.97, 1.59, "福冈客-0.0 @1.875"),
]
N = 200_000
rng = np.random.default_rng(7)
all_modes = {}
for name, lh, la, bet in MATCHES:
    h = rng.poisson(lh, N)
    a = rng.poisson(la, N)
    keys = h * 100 + a
    uniq, cnt = np.unique(keys, return_counts=True)
    order = np.argsort(-cnt)
    top = [(u // 100, u % 100, c / N) for u, c in zip(uniq[order][:6], cnt[order][:6])]
    mode = top[0]
    total = h + a
    ov25 = (total > 2.5).mean()
    print("==== %s  (lambda %.2f/%.2f) %s" % (name, lh, la, ("| 注单: " + bet) if bet else ""))
    print("  众数比分: %d-%d  出现率 %.2f%%" % (mode[0], mode[1], mode[2] * 100))
    print("  前5比分: " + "  ".join("%d-%d(%.1f%%)" % (s[0], s[1], s[2] * 100) for s in top[1:6]))
    tot_mode = np.argmax(np.bincount(total))
    print("  总进球众数=%d球 | 模拟大2.5=%.1f%% 小2.5=%.1f%%" % (tot_mode, ov25 * 100, (1 - ov25) * 100))
    all_modes[name] = (mode[0], mode[1], mode[2])
print()
print("== 9场众数比分汇总 ==")
from collections import Counter
c = Counter((v[0], v[1]) for v in all_modes.values())
for k, v in c.most_common():
    print("  %d-%d 出现%d次(作为该场众数)" % (k[0], k[1], v))
