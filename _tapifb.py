import json, io, sys, requests
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
env = {}
for l in io.open('D:/足球分析/.env', encoding='utf-8-sig'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.split('=', 1)
        v = v.split('#')[0].strip().strip('"').strip("'")
        env[k.strip()] = v
H = {'x-apisports-key': env['FOOTBALL_API_KEY']}
r = requests.get('https://v3.football.api-sports.io/status', headers=H, timeout=30)
print('status:', r.status_code, r.text[:300])
