import json, io, sys, re, unicodedata, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1); v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
KEY = env['ODDS_API_KEY_6']
u = 'https://api.the-odds-api.com/v4/sports/soccer_france_ligue_one/scores/?apiKey=%s&daysFrom=2&dateFormat=iso' % KEY
r = requests.get(u, headers={'Accept':'application/json'}, timeout=40)
for ev in r.json():
    h = ev.get('home_team') or ''; a = ev.get('away_team') or ''
    if any(x in h+a for x in ('Rennes','Renn','PSG','Saint','Paris')):
        sc = {s['name']: s['score'] for s in (ev.get('scores') or [])}
        print(ev.get('home_team'), 'vs', ev.get('away_team'), '| scores:', sc, '| completed:', ev.get('completed'), '| commence:', ev.get('commence_time'))
