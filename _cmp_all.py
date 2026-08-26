import json
old = json.load(open('analysis_records/scan_next24h_20260824_2321.json', encoding='utf-8'))
new = json.load(open('analysis_records/scan_next24h_20260825_0021.json', encoding='utf-8'))
def key(m): return (m['ko_bjt'], m['home'], m['away'])
bo = {key(m): m for m in old}
bn = {key(m): m for m in new}
print('场次数: 旧', len(bo), '新', len(bn))
diff = 0
for k in sorted(set(bo) & set(bn)):
    o, b = bo[k], bn[k]
    ob, nb = o.get('best_bet'), b.get('best_bet')
    on, nn = (ob or {}).get('name'), (nb or {}).get('name')
    oe, ne = (ob or {}).get('ev'), (nb or {}).get('ev')
    os_, ns_ = (ob or {}).get('star'), (nb or {}).get('star')
    ov, nv = o.get('vetoed'), b.get('vetoed')
    if (on, oe, os_, ov) != (nn, ne, ns_, nv):
        diff += 1
        print('DIFF:', k[0], o['home'], 'vs', o['away'])
        print('  旧:', on, round(oe*100,1) if oe is not None else None, os_, 'veto:', ov)
        print('  新:', nn, round(ne*100,1) if ne is not None else None, ns_, 'veto:', nv)
print('总差异:', diff)
