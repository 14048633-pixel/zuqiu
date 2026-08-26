# -*- coding: utf-8 -*-
import json, csv, datetime
arch = json.load(open('analysis_records/20260815_scan_upcoming.json', encoding='utf-8'))
rows = list(csv.DictReader(open('analysis_records/bet_ledger.csv', encoding='utf-8-sig')))
pend = [r for r in rows if r.get('status') == '待结算']
def norm(s): return ''.join(c.lower() for c in s if c.isalnum())
m_by_key = {}
for m in arch['matches']:
    m_by_key[(m['league'], norm(m['home']), norm(m['away']))] = m
def f(x):
    try: return float(x)
    except: return 0.0
BJT = datetime.timezone(datetime.timedelta(hours=8))
out = []
for r in pend:
    m = m_by_key.get((r.get('league'), norm(r.get('home', '')), norm(r.get('away', ''))))
    tags = list(m['result'].get('risk_tags', [])) if (m and m.get('result')) else []
    veto = [t for t in tags if '否决' in t]
    ct = m.get('ct', '') if m else ''
    bt = ''
    if ct:
        ko = datetime.datetime.fromisoformat(ct.replace('Z', '+00:00'))
        bt = ko.astimezone(BJT).strftime('%m-%d %H:%M')
    out.append({
        'bt': bt, 'league': r.get('league'), 'home': r.get('home'), 'away': r.get('away'),
        'bet': r.get('bet_name'), 'prob': r.get('prob'), 'odds': r.get('odds'),
        'ev': float(r.get('ev') or 0), 'star': r.get('star'), 'tier': r.get('ev_tier'),
        'veto': ';'.join(veto) if veto else '',
    })
out.sort(key=lambda x: (bool(x['veto']), x['bt']))
lines = []
lines.append('# 85场待结算注单完整明细')
lines.append('')
lines.append('生成: ' + datetime.datetime.now(BJT).strftime('%Y-%m-%d %H:%M') + ' 北京时间 | 目标300场 | 台账103(已结算18)')
lines.append('')
lines.append('> 否决=最新硬否决规则(盘口距开赛>12h/隔日快照/模型vs市场分歧>20pp)下本场已触发否决。')
lines.append('')
nv = [o for o in out if not o['veto']]
v = [o for o in out if o['veto']]
lines.append('## 未否决 ' + str(len(nv)) + ' 场')
lines.append('')
lines.append('| 开球(北京) | 联赛 | 对阵 | 注单 | 概率 | 赔率 | EV | 星 | 分层 |')
lines.append('|---|---|---|---|---|---|---|---|---|')
for o in nv:
    lines.append('| %s | %s | %s vs %s | %s | %s | %s | %+.1f%% | ★%s | %s |' % (
        o['bt'], o['league'], o['home'], o['away'], o['bet'], o['prob'], o['odds'],
        o['ev'] * 100, o['star'], o['tier']))
lines.append('')
lines.append('## 触发否决 ' + str(len(v)) + ' 场')
lines.append('')
lines.append('| 开球(北京) | 联赛 | 对阵 | 注单 | 赔率 | EV | 星 | 否决原因 |')
lines.append('|---|---|---|---|---|---|---|---|')
for o in v:
    reason = o['veto'][:40]
    lines.append('| %s | %s | %s vs %s | %s | %s | %+.1f%% | ★%s | %s |' % (
        o['bt'], o['league'], o['home'], o['away'], o['bet'], o['odds'],
        o['ev'] * 100, o['star'], reason))
lines.append('')
lines.append('## 汇总')
lines.append('')
lines.append('- 未否决 28 场: 高价值★3 11 / 高价值★2 3 / 标准★2 8 / 标准★1 3 / 观察★1 3')
lines.append('- 触发否决 57 场: 盘口过期/隔日快照为主, 模型vs市场分歧>20pp 9 场')
lines.append('- 注意: 这批85场在硬否决规则上线前落账, 57场本应按新纪律剔除; 结算时需区分统计')
with open('analysis_records/ledger_pending_85_detail.md', 'w', encoding='utf-8') as fp:
    fp.write('\n'.join(lines))
print('written lines:', len(lines))
