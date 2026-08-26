import json, io, sys, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = 'https://sports.bzzoiro.com'
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1); v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
H = {'User-Agent': 'Mozilla/5.0', 'Authorization': 'Token ' + env['BZZOIRO_API_KEY']}
for tid, tag in ((4577,'La Serena'), (760,'Cobresal'), (744,'Palestino'), (1393,'Palermo'), (1606,'Juve Stabia'), (2099,'TPS')):
    u = BASE + '/api/v2/events/?team_id=%d&status=finished&date_from=2026-08-22&date_to=2026-08-25' % tid
    d = requests.get(u, headers=H, timeout=40).json()
    for ev in (d.get('results') or []):
        print(tag, '->', ev.get('home_team'), 'vs', ev.get('away_team'), ev.get('home_score'), ev.get('away_score'), ev.get('status'))
# O Higgins via team_name
for q in ('Higgins', 'O%27Higgins'):
    u = BASE + '/api/v2/events/?team_name=%s&status=finished&date_from=2026-08-22&date_to=2026-08-25' % q
    d = requests.get(u, headers=H, timeout=40).json()
    for ev in (d.get('results') or []):
        print('Q', q, '->', ev.get('home_team'), 'vs', ev.get('away_team'), ev.get('home_score'), ev.get('away_score'))
