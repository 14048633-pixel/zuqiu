import json
from datetime import datetime, timezone
d = json.load(open('_replay_live_feature_out.json', encoding='utf-8'))
def pdt(s):
    try:
        x = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        if x.tzinfo is None: x = x.replace(tzinfo=timezone.utc)
        return x
    except Exception: return None

def age_h(x, side):
    s = (x.get(side) or {}).get('snap')
    ct = pdt(x.get('kickoff'))
    st = pdt(s)
    if not ct or not st: return None
    return (ct - st).total_seconds() / 3600

def hit(rs, side='live'):
    rows = []
    for x in rs:
        s = x.get(side) or {}
        if s.get('best') and s.get('result') in ('win', 'half', 'lose'):
            rows.append(s)
    n = len(rows)
    if not n: return (0, 0, 0, 0, 0)
    win = sum(1 for s in rows if s['result'] in ('win', 'half'))
    dec = win + sum(1 for s in rows if s['result'] == 'lose')
    pnl = sum((s.get('pnl') or 0) for s in rows)
    return (n, win, dec, win / dec * 100 if dec else 0, pnl / n * 100 if n else 0)

def show(rs, label, side='live'):
    n, w, dec, hh, roi = hit(rs, side)
    print('%-40s n=%3d 命中=%d/%d=%5.1f%% ROI=%+6.1f%%' % (label, n, w, dec, hh, roi))

print('== 临场快照有效(距开赛<=12h)场次 ==')
lv = [x for x in d if (age_h(x, 'live') or 999) <= 12]
print('场次数:', len(lv))
show(lv, '临场 BEST 出单(<=12h)', 'live')
# 同场 早盘也有效(<=12h)
both = [x for x in lv if (age_h(x, 'early') or 999) <= 12]
show(both, '  其中早盘也<=12h: 临场BEST', 'live')
show(both, '  其中早盘也<=12h: 早盘BEST', 'early')
# 早盘过期(>12h被否决)但临场有效
rescued = [x for x in lv if (age_h(x, 'early') or 0) > 12]
show(rescued, '早盘过期->临场救回: 临场BEST', 'live')
print('  早盘过期->临场救回场次数:', len(rescued))
# 强临场 <=3h
v3 = [x for x in d if (age_h(x, 'live') or 999) <= 3]
show(v3, '强临场(<=3h) BEST 出单', 'live')
print()
print('== 全量对比(含过期) 参考 ==')
show(d, '临场 BEST 出单(全)', 'live')
show(d, '早盘 BEST 出单(全)', 'early')
