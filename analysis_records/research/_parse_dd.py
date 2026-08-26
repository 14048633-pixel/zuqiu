# -*- coding: utf-8 -*-
import sys, io, re
sys.stdout.reconfigure(encoding='utf-8')
txt = io.open('analysis_records/direction_detail_20260820.txt', encoding='utf-8').read()
# 分段统计
sections = re.split(r'\n(?=【)', txt)
print('段数:', len(sections))
for sec in sections:
    sec = sec.strip()
    if not sec: continue
    m = re.match(r'【(.+?)】\s*(\d+)\s*场\s*\|?\s*命中率\s*([\d.]+)%', sec)
    if m:
        name, n, rate = m.group(1), int(m.group(2)), float(m.group(3))
        # 数实际行
        lines = [l for l in sec.split('\n')[1:] if l.startswith(('✅','❌','➖','½'))]
        win = sum(1 for l in lines if l.startswith('✅'))
        print('%s | 声明%d场 命中率%s%% | 实际行%d 命中%d' % (name, n, rate, len(lines), win))
    else:
        print('未解析:', sec[:60].replace('\n',' '))
