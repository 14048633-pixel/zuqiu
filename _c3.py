import csv, io, sys
from collections import Counter
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
rows = list(csv.DictReader(io.open(r'analysis_records/bet_ledger.csv', encoding='utf-8-sig')))
hs = sum(1 for r in rows if (r.get('home_score') or '').strip())
print('总行:', len(rows), '有home_score:', hs)
ou = [r for r in rows if (r.get('bet_name') or '').startswith(('大','小'))]
print('大小球:', len(ou), '其中含比分:', sum(1 for r in ou if (r.get('home_score') or '').strip()))
print('含比分行样例:')
n=0
for r in ou:
    if (r.get('home_score') or '').strip():
        print(' ', r.get('league'), r.get('match'), r.get('bet_name'), r.get('home_score'), r.get('away_score'), r.get('result'), r.get('status'))
        n+=1
        if n>=10: break
