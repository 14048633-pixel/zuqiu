import json, io, sys, re, collections
from datetime import datetime, timezone, timedelta
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
miss = json.load(io.open('_miss_list.json', encoding='utf-8'))
CST = timezone(timedelta(hours=8))
now = datetime(2026, 8, 24, 9, 0, tzinfo=CST)
def parse_ct(ct):
    if not ct: return None
    ct = str(ct)
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})T?', ct)
    if m:
        try:
            return datetime.fromisoformat(ct.replace('Z','+00:00')).astimezone(CST)
        except Exception:
            return None
    m2 = re.match(r'^(\d{2})-(\d{2}) (\d{2}):(\d{2})', ct)
    if m2:
        try:
            return datetime(2026, int(m2.group(1)), int(m2.group(2)), int(m2.group(3)), int(m2.group(4)), tzinfo=CST)
        except Exception:
            return None
    return None
passed = [r for r in miss if (parse_ct(r['ct']) or now) <= now]
future = [r for r in miss if (parse_ct(r['ct']) or now) > now]
nofmt = [r for r in miss if parse_ct(r['ct']) is None]
print('已过开赛时间缺结果:', len(passed))
print('未来比赛(正常缺结果):', len(future))
print('时间格式异常:', len(nofmt))
by = collections.Counter(r['league'] for r in passed)
print('已过场次按联赛:', dict(by.most_common(30)))
io.open('_miss_passed.json','w',encoding='utf-8').write(json.dumps(passed, ensure_ascii=False, indent=1))
