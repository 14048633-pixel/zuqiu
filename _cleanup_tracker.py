# -*- coding: utf-8 -*-
"""清理 live_tracker: 删 4 条重复旧id(同场#ou已结算) + 补结 2 条纯漏."""
import io, sys, json, shutil, datetime, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
fp = r'D:\发家致富\strategy_data\live_tracker.json'
bak = fp + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copy(fp, bak)
print('备份:', bak)

recs = json.load(open(fp, encoding='utf-8'))

# 1) 删除 4 条重复旧 id(无#ou, 且同场存在已结算的 #ou 版本)
dup_ids = [
    '2026-09-03_SAU_Al-Fayha_vs_Al-Kholood',
    '2026-09-03_POL_Raków Częstochowa_vs_Górnik Zabrze',
    '2026-09-03_SAU_Neom SC_vs_Al-Khaleej',
    '2026-09-03_SW1_Basel_vs_FC Sion',
]
before = len(recs)
recs = [r for r in recs if r['id'] not in dup_ids]
print('删除重复旧 id:', len(recs) - before, '条 -> 剩', len(recs))

# 2) 补结 2 条纯漏: Toulouse 小2.5 (0-1), Cagliari 大2.5 (1-2)
def settle_one(rec, hg, ag):
    total = hg + ag
    over = str(rec.get('pick', '')).startswith('大')
    price = rec.get('odds') or []
    price = price[0] if price else None
    if not price or price <= 1:
        rec['status'] = 'void'; rec['profit_pct'] = None
        return
    if (total > 2.5) if over else (total < 2.5):
        rec['status'] = 'won'; rec['profit_pct'] = round(price - 1.0, 4)
    else:
        rec['status'] = 'lost'; rec['profit_pct'] = -1.0
    rec['actual_hg'] = hg; rec['actual_ag'] = ag
    rec['settled_date'] = '2026-09-04'

fix_map = {
    '2026-09-03_F1_Toulouse_vs_Lille': (0, 1),       # 小2.5 -> total 1 -> won
    '2026-09-03_I1_Cagliari_vs_Hellas Verona': (1, 2),  # 大2.5 -> total 3 -> won
}
for r in recs:
    if r['id'] in fix_map and r['status'] == 'open':
        settle_one(r, *fix_map[r['id']])
        print('补结:', r['id'], r['pick'], '%d-%d' % fix_map[r['id']], r['status'], r['profit_pct'])

json.dump(recs, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('总记录:', len(recs))

# 3) 重出报告
sys.path.insert(0, r'D:\发家致富\football_analyzer')
from tracker import report
rep = report()
print(json.dumps(rep, ensure_ascii=False, indent=2))
