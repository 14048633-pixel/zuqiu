import json
old = json.load(open('analysis_records/scan_next24h_20260824_2321.json', encoding='utf-8'))
new = json.load(open('analysis_records/scan_next24h_20260825_0020.json', encoding='utf-8'))
def key(m): return (m['ko_bjt'], m['home'], m['away'])
bo = {key(m): m for m in old}
bn = {key(m): m for m in new}
print('== BEST 对比 (旧the-odds vs 新BSD-h2h) ==')
for k in sorted(set(bo) & set(bn)):
    o, b = bo[k], bn[k]
    ob, nb = o.get('best_bet'), b.get('best_bet')
    if ob or nb:
        ov = round(ob['ev'] * 100, 1) if ob else None
        nv = round(nb['ev'] * 100, 1) if nb else None
        mark = '' if (ob or {}).get('name') == (nb or {}).get('name') and ov == nv else '  <== 变化'
        print(k[0], o['home'], 'vs', o['away'])
        print('   旧:', (ob or {}).get('name'), 'EV', ov, 'star', (ob or {}).get('star'))
        print('   新:', (nb or {}).get('name'), 'EV', nv, 'star', (nb or {}).get('star'), mark)
