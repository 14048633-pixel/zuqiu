import json, io, sys, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = 'https://sports.bzzoiro.com'
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1); v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
H = {'User-Agent': 'Mozilla/5.0', 'Authorization': 'Token ' + env['BZZOIRO_API_KEY']}
for tid, tag in ((4577,'La Serena'), (1393,'Palermo')):
    u = BASE + '/api/v2/teams/%d/fixtures/?date_from=2026-08-20&date_to=2026-08-26' % tid
    d = requests.get(u, headers=H, timeout=40).json()
    print('===', tag, 'fixtures:', json.dumps(d, ensure_ascii=False)[:600])
