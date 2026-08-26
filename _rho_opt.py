# -*- coding: utf-8 -*-
import sys, io, json
sys.path.insert(0, r'src/models')
from poisson_lambda import dixon_coles_prob

cal = json.load(io.open(r'strategy_data/league_calib.json', encoding='utf-8'))['leagues']
target = {
  '西甲': (2.581, 45.7, 26.0, 28.2), '西乙': (2.441, 45.0, 30.1, 24.9),
  '荷甲': (3.688, 45.3, 23.6, 31.1), '英冠': (2.692, 43.2, 26.7, 30.1),
  '法甲': (2.762, 43.8, 25.6, 30.7), '德乙': (3.049, 43.1, 27.1, 29.8),
  '英超': (2.872, 44.3, 23.7, 32.0), '德甲': (3.165, 44.2, 24.7, 31.1),
  '意甲': (2.697, 42.3, 25.5, 32.2),
}
def err(h, a, rho, tg):
    avg, th, td, ta = tg
    sp, mp = dixon_coles_prob(avg/2.0*h, avg/2.0*a, rho)
    return abs(mp['win']*100-th) + abs(mp['draw']*100-td) + abs(mp['lose']*100-ta)

best = {}
for lg, tg in target.items():
    cands = []
    for h in (1.00, 1.05, 1.08, 1.10, 1.12, 1.15, 1.18, 1.20, 1.22, 1.25):
        for a in (0.85, 0.88, 0.90, 0.92, 0.95):
            for rho in (-0.10, -0.08, -0.05, -0.04, 0.0):
                cands.append((err(h, a, rho, tg), h, a, rho))
    cands.sort()
    best[lg] = cands[:3]

for lg, cands in best.items():
    avg, th, td, ta = target[lg]
    print(lg)
    for e, h, a, rho in cands:
        sp, mp = dixon_coles_prob(avg/2.0*h, avg/2.0*a, rho)
        print('  H%.2f A%.2f ρ%+.2f | 误差%.2f -> 模型H%.1f/D%.1f/A%.1f (实际%.1f/%.1f/%.1f)' % (
            h, a, rho, e, mp['win']*100, mp['draw']*100, mp['lose']*100, th, td, ta))
