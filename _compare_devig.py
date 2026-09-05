# -*- coding: utf-8 -*-
"""P1 回测对比: devig3(简单归一) vs devig_shin(Shin 法) 在真实赔率上的差异
样本: 从最新 batch 输出提取真实赔率组合(1X2 市场), 对比两种去水的 market_wdl 与 EV 差。
"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'D:\发家致富\football_analyzer')
os.chdir(r'D:\发家致富\football_analyzer')
from shin_devig import devig_shin, devig3

# 从最新输出提取真实 1X2 赔率: 反推原始赔率不可行, 用已知真实样本(BSD/theoddsapi 实测)
# 真实样本来自本会话盘源实测 + 输出 market_wdl 反推组合
samples = [
    ("QPR vs Middlesbrough (theoddsapi)", (3.17, 3.47, 2.14)),
    ("Al-Fayha vs Al-Kholood (BSD)", (2.20, 3.40, 3.30)),
    ("Basel vs Sion (BSD)", (2.05, 3.60, 3.40)),
    ("Lugano vs Servette (BSD)", (1.95, 3.70, 3.60)),
    ("Grêmio vs Internacional (BSD)", (2.40, 3.20, 3.00)),
    ("Raków vs Górnik (BSD)", (2.00, 3.30, 3.80)),
    ("典型大热门 (假设)", (1.31, 5.20, 9.50)),
    ("典型均衡 (假设)", (2.55, 3.30, 2.80)),
]

print("%-42s %-28s %-28s %s" % ("场次", "devig3 主/平/客", "shin 主/平/客", "EV差(主)"))
print("-" * 130)
tot = 0.0
for name, odds in samples:
    r3 = devig3(*odds)
    rs = devig_shin(*odds)
    # 假设模型概率 = devig3 概率 + 2pp 优势(模拟模型略高于市场)
    mp = r3[0] + 0.02
    ev3 = mp * odds[0] - 1.0
    evs = mp * odds[0] - 1.0  # 模型概率不变, 但市场概率变了 -> 真实 EV 不同
    # 更合理对比: 用同一模型概率, 对比"相对市场"的 edge
    d3 = "%.3f/%.3f/%.3f" % (r3[0], r3[1], r3[2])
    ds = "%.3f/%.3f/%.3f" % (rs[0], rs[1], rs[2])
    d_home = (rs[0] - r3[0]) * 100
    tot += abs(d_home)
    print("%-42s %-28s %-28s 主%+.2fpp" % (name, d3, ds, d_home))

print("-" * 130)
print("平均主胜概率偏移幅度: %.3f pp (Shin 相对简单归一)" % (tot / len(samples)))

# 展示: 一个具体例子 EV 计算差异(用 QPR 场, 模型概率=60% 场景)
h, d, a = samples[0][1]
for mp_label, mp in (("模型主胜60%", 0.60), ("模型主胜55%", 0.55)):
    f3 = devig3(h, d, a)[0]
    fs = devig_shin(h, d, a)[0]
    ev3 = mp * h - 1.0
    edge3 = (mp - f3) * 100
    edges = (mp - fs) * 100
    print("QPR: 模型%s -> edge(devig3)=%+.2fpp, edge(shin)=%+.2fpp, 差%+.2fpp"
          % (mp_label, edge3, edges, edges - edge3))
