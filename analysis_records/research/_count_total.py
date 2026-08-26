# -*- coding: utf-8 -*-
import sys, io, re
sys.stdout.reconfigure(encoding='utf-8')
txt = io.open('analysis_records/direction_detail_20260820.txt', encoding='utf-8').read()
sections = re.split(r'\n(?=【)', txt)
matches = set()
for sec in sections:
    for l in sec.split('\n'):
        l = l.strip()
        if not l.startswith(('✅','❌','➖','½')): continue
        # 提取队名: 跳过日期字段后的 "| X vs Y |" 模式, 或 "联赛 日期 | 主 vs 客 | 方向 | 比分"
        # 尝试 主 vs 客
        m = re.search(r'\|\s*([^|]+?)\s+vs\s+([^|]+?)\s*\|', l)
        if m:
            matches.add((m.group(1).strip(), m.group(2).strip()))
print('历史唯一场次:', len(matches))
# 今日41场
import json
d37 = json.load(open('analysis_records/research/tonight37_review_20260821.json', encoding='utf-8'))
today = set()
for m in d37:
    today.add((m['h'], m['a']))
today.add(('Botafogo','Cienciano')); today.add(('Corinthians','Rosario Central'))
today.add(('Kashiwa Reysol','V-Varen Nagasaki')); today.add(('FC Tokyo','JEF United Chiba'))
print('今日41场唯一:', len(today))
overlap = matches & today
print('重叠:', len(overlap))
total = matches | today
print('总计唯一场次:', len(total))
