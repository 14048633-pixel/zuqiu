# -*- coding: utf-8 -*-
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
d=json.load(io.open(r'analysis_records\scan_next24h_20260826_1349.json',encoding='utf-8'))
print('未来24小时扫描: %d 场' % len(d))
print()
for r in d:
    if r.get('error'):
        print('  %-16s %-6s %-24s vs %-24s | ERROR %s' % (r['ko_bjt'],r['league'],(r['home'] or '')[:22],(r['away'] or '')[:22],str(r['error'])[:60]))
        continue
    bb=r.get('best_bet')
    bbs=''
    if bb:
        st=bb.get('star')
        st=st.get('level') if isinstance(st,dict) else st
        bbs=' | BEST:%s EV%+.1f%% ★%s' % (bb['name'],(bb.get('ev') or 0)*100,st)
    dw=r.get('draw_warn')
    if isinstance(dw,dict):
        dw=dw.get('level') or dw.get('value') or dw.get('prob') or ''
    warn=(' | ⚠平局:%s' % dw) if dw else ''
    lam=(r.get('lambda') or {})
    ls=lam.get('sum') if isinstance(lam,dict) else None
    print('  %-16s %-6s %-24s vs %-24s | 方向:%-8s %+5.1f%% | λ%s%s%s' % (
        r['ko_bjt'], r['league'], (r['home'] or '')[:22], (r['away'] or '')[:22],
        r.get('direction') or '无', (r.get('dir_ev') or 0)*100,
        ('%.2f'%ls) if isinstance(ls,(int,float)) else '-', bbs, warn))
