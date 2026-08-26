import json, io, sys, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = 'https://sports.bzzoiro.com'
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1); v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
H = {'User-Agent': 'Mozilla/5.0', 'Authorization': 'Token ' + env['BZZOIRO_API_KEY']}
for q in ('La Serena','Cobresal','O Higgins','Palestino','Palermo','Juve Stabia','Turun Palloseura'):
    d = requests.get(BASE + '/api/v2/teams/?name=%s' % q, headers=H, timeout=40).json()
    for x in (d.get('results') or [])[:4]:
        print(q, '->', x.get('id'), x.get('name'), x.get('short_name'), x.get('country'))
