import csv, collections
from datetime import datetime, timezone

snap_rows = []
with open('prediction_v2/output/odds_snapshots/snapshots.csv', encoding='utf-8', errors='replace') as f:
    rd = csv.reader(f); next(rd)
    for r in rd: snap_rows.append(r)

def parse_dt(s):
    try:
        d = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None

def nm(s):
    import unicodedata, re
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', s.lower())

by_match = collections.defaultdict(set)
for r in snap_rows:
    ct = parse_dt(r[3]); st = parse_dt(r[0])
    if not ct or not st or st > ct:
        continue
    key = (r[2], nm(r[4]), nm(r[5]), ct.isoformat())
    by_match[key].add(r[0])

led = []
with open('analysis_records/bet_ledger.csv', encoding='utf-8-sig', errors='replace') as f:
    for r in csv.DictReader(f): led.append(r)
best = [r for r in led if r.get('status') == '已结算' and (r.get('star') or '') not in ('', '0')]

ok2 = ok1 = no = 0
for r in best:
    kf = r.get('kickoff') or ''
    ct = parse_dt(kf.replace('+08:00', '+00:00')) if '+08:00' in kf else parse_dt(kf)
    if ct is None and kf:
        try:
            d = datetime.fromisoformat(kf.replace('+08:00', ''))
            ct = d.replace(tzinfo=timezone(timedelta(hours=8))).astimezone(timezone.utc)
        except Exception:
            ct = None
    key = (r.get('league'), nm(r.get('home')), nm(r.get('away')), ct.isoformat() if ct else '')
    ts = by_match.get(key) or set()
    if len(ts) >= 2: ok2 += 1
    elif len(ts) == 1: ok1 += 1
    else: no += 1

print('BEST已结算(star>=1):', len(best))
print('  >=2赛前快照时点(可早盘vs临场):', ok2)
print('  =1赛前快照时点:', ok1)
print('  无快照匹配:', no)
