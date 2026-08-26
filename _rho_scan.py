# -*- coding: utf-8 -*-
import sys, io, json
sys.path.insert(0, r'src/models')
from poisson_lambda import dixon_coles_prob

cal = json.load(io.open(r'strategy_data/league_calib.json', encoding='utf-8'))['leagues']

def wdl(avg, home, away, rho):
    a = avg/2.0
    sp, mp = dixon_coles_prob(a*home, a*away, rho)
    return mp['win']*100, mp['draw']*100, mp['lose']*100

targets = {
    '英超': (2.872, 1.10, 0.95, 0.0, 38.7, 32.0, 29.4),
    '西甲': (2.581, 1.10, 0.95, 0.0, 50.7, 23.9, 25.4),
    '挪超': (2.946, 1.05, 0.95, -0.04, 50.0, 19.9, 30.1),
    '美职': (3.016, 1.10, 0.95, -0.04, 49.1, 23.2, 27.7),
    '阿甲': (1.885, 1.08, 0.95, -0.04, 44.5, 27.4, 28.0),
    '意乙': (2.595, 1.08, 0.95, -0.04, 46.7, 29.0, 24.3),
    '西乙': (2.441, 1.10, 0.95, -0.04, 47.4, 23.5, 29.1),
    '荷甲': (3.688, 1.05, 0.95, 0.0, 42.0, 27.0, 31.0),
    '英冠': (2.692, 1.10, 0.95, -0.05, 39.5, 26.0, 34.5),
    '巴甲': (2.572, 1.08, 0.95, -0.05, 45.5, 29.5, 25.0),
}
print('== 当前配置 vs 实际 ==')
for lg, (avg, h, a, rho, ah, ad, aa) in targets.items():
    mh, md, ma = wdl(avg, h, a, rho)
    print('%-4s cfg(%+.2f/%+.2f rho%+.2f) H%.1f/D%.1f/A%.1f | 实H%.1f/D%.1f/A%.1f | ΔH%+.1f ΔD%+.1f' % (lg, h, a, rho, mh, md, ma, ah, ad, aa, ah-mh, ad-md))
print()
print('== 扫描: 英超 ρ (平局32%) ==')
for rho in (0.0, -0.08, -0.12, -0.15, -0.18, -0.20):
    mh, md, ma = wdl(2.872, 1.10, 0.95, rho)
    print('  rho=%+.2f -> H%.1f/D%.1f/A%.1f' % (rho, mh, md, ma))
print()
print('== 扫描: 西甲 home (主胜50.7%) ==')
for h in (1.10, 1.15, 1.20, 1.25, 1.30):
    mh, md, ma = wdl(2.581, h, 0.95, 0.0)
    print('  home=%+.2f -> H%.1f/D%.1f/A%.1f' % (h, mh, md, ma))
print()
print('== 扫描: 荷甲 ρ (平局27%) ==')
for rho in (0.0, -0.05, -0.08, -0.10, -0.12):
    mh, md, ma = wdl(3.688, 1.05, 0.95, rho)
    print('  rho=%+.2f -> H%.1f/D%.1f/A%.1f' % (rho, mh, md, ma))
