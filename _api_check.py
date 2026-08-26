import sys, os, requests
sys.stdout.reconfigure(encoding='utf-8')
os.chdir('D:/ai/电脑庄家/足球竞猜模型训练')
from dotenv import load_dotenv
load_dotenv('.env')
FOOTBALL_API_KEY = os.getenv('FOOTBALL_API_KEY')
print('API key存在:', bool(FOOTBALL_API_KEY), '长度:', len(FOOTBALL_API_KEY or ''))
if not FOOTBALL_API_KEY:
    print('无法查API, 需要用户提供数据')
    sys.exit()
headers = {'x-apisports-key': FOOTBALL_API_KEY}
r = requests.get('https://v3.football.api-sports.io/teams', headers=headers, params={'search': 'Gimpo'}, timeout=30)
print('状态:', r.status_code)
print('结果:', r.text[:400])
