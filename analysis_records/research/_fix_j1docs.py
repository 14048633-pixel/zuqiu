# -*- coding: utf-8 -*-
import io, sys
sys.stdout.reconfigure(encoding='utf-8')
# 1) betting_strategy.py 注释
p = 'src/strategy/betting_strategy.py'
s = io.open(p, encoding='utf-8').read()
old = '# 日本J1 - 2026跨年赛季, 场均2.4球, 主场优势中等, 偏小球 (2026真值)'
new = '# 日本J1 - 2026-27跨年新规(外援5人/取消U23强制), 开季20场实测场均3.35/大2.5=70%/主客中性 (官方2.40已弃用)'
if old in s:
    s = s.replace(old, new)
    io.open(p, 'w', encoding='utf-8').write(s)
    print('betting_strategy.py 注释已更新')
else:
    print('betting_strategy.py 未找到旧注释')
# 2) AGENTS.md J1 改制对比 2.40 描述
p2 = 'AGENTS.md'
s2 = io.open(p2, encoding='utf-8').read()
old2 = '新跨年正式赛季(20队2.40球)'
new2 = '新跨年正式赛季(20队, 官方预设2.40已弃用, 开季20场实测3.35/大2.5=70%/主40客40)'
if old2 in s2:
    s2 = s2.replace(old2, new2)
    io.open(p2, 'w', encoding='utf-8').write(s2)
    print('AGENTS.md 已更新')
else:
    print('AGENTS.md 未找到目标串')
