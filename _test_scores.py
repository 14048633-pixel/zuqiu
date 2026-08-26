import json, io, sys, os, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
# load key6
KEY = ''
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if l.startswith('ODDS_API_KEY_6='):
        KEY = l.split('=', 1)[1].strip().strip('"').strip("'")
print('key6 len:', len(KEY))
BASE = 'https://api.the-odds-api.com/v4'
u = '%s/sports/soccer_turkey_super_league/scores/?apiKey=%s&daysFrom=1&dateFormat=iso' % (BASE, KEY)
r = requests.get(u, headers={'Accept': 'application/json'}, timeout=30)
print('status:', r.status_code)
print('remaining:', r.headers.get('x-requests-remaining'))
try:
    d = r.json()
    if isinstance(d, list):
        print('rows:', len(d))
        for ev in d[:3]:
            print(json.dumps(ev, ensure_ascii=False)[:300])
    else:
        print(str(d)[:300])
except Exception as e:
    print('ERR', repr(e), r.text[:200])
