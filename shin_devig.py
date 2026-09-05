# -*- coding: utf-8 -*-
"""Shin 法去水 (P1, 2026-09-03 接入).

算法: Shin (1992/1993) 假设市场含比例 z 的知情交易者, 庄家对此设防(overround 偏向冷门).
实现: Jullien & Salanié (1994) 迭代法求 z, 参考 R CRAN `implied` 包 shin_func / js 迭代.

对比: 简单归一(devig3)把 overround 均摊, 会系统性低估热门/高估冷门;
      Shin 法按"知情资金比例"还原真实概率, 对小联赛/大 margin 场更准.

用法: devig_shin(h, d, a) -> (ph, pd, pa), 和恒为 1.
      devig3(h, d, a) 保留作极端情形 fallback(Shin 异常/不收敛时)。
"""
from __future__ import annotations
import math


def devig_shin(h, d, a, max_iter=1000, tol=1e-10):
    """Shin 法去水, 返回 (ph, pd, pa) 三元组, 和=1 (归一化后).

    参考 R implied::implied_probabilities(method='shin', shin_method='js')
    """
    io = [1.0 / h, 1.0 / d, 1.0 / a]
    s = sum(io)
    n = len(io)
    if not all(x > 0 for x in io) or s <= 0:
        return [x / s for x in io]
    # 迭代求 z (Jullien & Salanie 1994)
    z = 0.0
    for _ in range(max_iter):
        z_prev = z
        z = (sum(math.sqrt(z_prev * z_prev + 4.0 * (1.0 - z_prev) * (x * x / s)) for x in io) - 2.0) / (n - 2.0)
        if abs(z - z_prev) <= tol:
            break
    # 安全钳位 z in [0, 0.5]
    z = max(0.0, min(z, 0.5))
    # shin_func: p_i = (sqrt(z^2 + 4(1-z)(io_i^2/s)) - z) / (2(1-z))
    probs = [(math.sqrt(z * z + 4.0 * (1.0 - z) * (x * x / s)) - z) / (2.0 * (1.0 - z)) for x in io]
    sp = sum(probs)
    if not (sp > 0 and all(p >= 0 for p in probs)):
        return [x / s for x in io]
    return [p / sp for p in probs]


def devig3(h, d, a):
    """简单去水(1/odds 归一), 保留作 fallback / 对照."""
    ih, id_, ia = 1.0 / h, 1.0 / d, 1.0 / a
    s = ih + id_ + ia
    return ih / s, id_ / s, ia / s


if __name__ == "__main__":
    # 对照 mberk/shin 官方示例: [2.6, 2.4, 4.3] -> [0.372994, 0.404779, 0.222227]
    exp = [0.37299406033208965, 0.4047794109200184, 0.2222265287474275]
    r = devig_shin(2.6, 2.4, 4.3)
    ok = all(abs(a - b) < 1e-6 for a, b in zip(r, exp))
    print("devig_shin(2.6,2.4,4.3) =", [round(x, 6) for x in r], "| 与 mberk 官方一致:", ok)
    assert ok, "Shin 实现与参考不一致!"
    # 与简单归一对比: 大 margin 下 Shin 更倾向热门
    r3 = devig3(2.6, 2.4, 4.3)
    print("devig3(2.6,2.4,4.3)   =", [round(x, 6) for x in r3])
    print("差异: 主%.4f 平%.4f 客%.4f" % (r[0]-r3[0], r[1]-r3[1], r[2]-r3[2]))
    print("self-test PASS")
