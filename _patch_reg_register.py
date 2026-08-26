# -*- coding: utf-8 -*-
import io
p = 'regression_test.py'
s = io.open(p, encoding='utf-8').read()
anchor = '    "test_star2_risk_rules",\n'
assert s.count(anchor) >= 1, s.count(anchor)
if 'test_draw_warn_plus_rules' not in s.split('TEST_ORDER =')[1].split(']')[0]:
    s = s.replace(anchor, anchor + '    "test_draw_warn_plus_rules",\n', 1)
    io.open(p, 'w', encoding='utf-8').write(s)
    print('registered test_draw_warn_plus_rules')
else:
    print('already registered')
