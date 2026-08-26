import json, io, sys
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
got = json.load(io.open('_win55_filled.json', encoding='utf-8'))
extra = [
 {'league':'瑞甲','home':'IK Brage','away':'Nordic United FC','ct':'2026-08-23T13:00:00+00:00','score':'1-2'},
 {'league':'瑞甲','home':'Norrby IF','away':'Sandvikens IF','ct':'2026-08-23T15:00:00+00:00','score':'1-1'},
 {'league':'soccer_germany_bundesliga_women','home':'RB Leipzig','away':'Bayer Leverkusen','ct':'2026-08-23T14:00:00+00:00','score':'0-2'},
 {'league':'soccer_germany_bundesliga_women','home':'Hamburger SV','away':'SC Freiburg','ct':'2026-08-23T16:30:00+00:00','score':'1-1'},
 {'league':'法甲','home':'Rennes','away':'Paris Saint Germain','ct':'2026-08-23T18:45:00+00:00','score':'2-2'},
]
allg = got + extra
print('补齐总数:', len(allg))
# 去重(按联赛+队名)
seen = set(); uniq = []
for r in allg:
    k = (r['league'], r['home'], r['away'])
    if k in seen: continue
    seen.add(k); uniq.append(r)
print('去重后:', len(uniq))
CST = timezone(timedelta(hours=8))
def key(r):
    try:
        return datetime.fromisoformat(r['ct'].replace('Z','+00:00')).astimezone(CST)
    except Exception:
        return datetime(2026,8,24,0,0,tzinfo=CST)
uniq.sort(key=key)
io.open(r'analysis_records/20260824_window_results.json','w',encoding='utf-8').write(json.dumps(uniq, ensure_ascii=False, indent=1))
print('saved analysis_records/20260824_window_results.json')
# 输出前40行
for r in uniq[:45]:
    ct = key(r)
    print(ct.strftime('%m-%d %H:%M'), r['league'], r['home'], 'vs', r['away'], r['score'])
