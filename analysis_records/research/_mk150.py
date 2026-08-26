# -*- coding: utf-8 -*-
import sys, io, re
sys.stdout.reconfigure(encoding='utf-8')
txt = io.open('analysis_records/direction_detail_20260820.txt', encoding='utf-8').read()
sections = re.split(r'\n(?=【)', txt)
out = []
for sec in sections:
    sec = sec.strip()
    if not sec: continue
    m = re.match(r'【(.+?)】', sec)
    if not m: continue
    header = sec.split('\n')[0]
    out.append('## ' + header)
    out.append('')
    out.append('| 结果 | 联赛 | 时间 | 对阵 | 方向 | 比分 |')
    out.append('|---|---|---|---|---|---|')
    for l in sec.split('\n')[1:]:
        l = l.strip()
        if not l.startswith(('✅','❌','➖','½')): continue
        res = {'✅':'✓','❌':'✗','➖':'走水','½':'半赢'}[l[0]]
        # 格式: 图标 联赛 时间 | 主 vs 客 | 方向 | 比分
        rest = l[1:].strip()
        # 拆 | 分隔
        parts = [p.strip() for p in rest.split('|')]
        if len(parts) >= 4:
            league = parts[0].split('  ')[0] if ' ' in parts[0] else parts[0]
            when = ' '.join(parts[0].split('  ')[1:]) if '  ' in parts[0] else ''
            matchup = parts[1]
            direction = parts[2]
            score = parts[3] if len(parts)>3 else ''
            out.append('| {} | {} | {} | {} | {} | {} |'.format(res, league, when.strip(), matchup, direction, score))
        elif len(parts) == 3:
            # J1 无日期
            league = parts[0]
            matchup = parts[1]
            direction = parts[2]
            out.append('| {} | {} | - | {} | {} | |'.format(res, league, matchup, direction))
    out.append('')
open('analysis_records/research/history150_directions.md','w',encoding='utf-8').write('\n'.join(out))
print('已生成: analysis_records/research/history150_directions.md')
print('行数:', len(out))
