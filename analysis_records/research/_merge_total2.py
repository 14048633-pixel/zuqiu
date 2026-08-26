# -*- coding: utf-8 -*-
import sys, io, re, json
sys.stdout.reconfigure(encoding='utf-8')
txt = io.open('analysis_records/direction_detail_20260820.txt', encoding='utf-8').read()
sections = re.split(r'\n(?=【)', txt)
hist = {}
for sec in sections:
    sec = sec.strip()
    if not sec: continue
    m = re.match(r'【(.+?)】\s*(\d+)\s*场', sec)
    if not m: continue
    lines = [l for l in sec.split('\n')[1:] if l.startswith(('✅','❌','➖','½'))]
    win = sum(1 for l in lines if l.startswith('✅'))
    half = sum(1 for l in lines if l.startswith('½'))
    hist[m.group(1)] = dict(n=len(lines), win=win, half=half)

# 今日37场: 逐腿统计 (含走水单独计)
d37 = json.load(open('analysis_records/research/tonight37_review_20260821.json', encoding='utf-8'))
def stat37():
    s = {'1X2主':[0,0], '1X2客':[0,0], '1X2平':[0,0], '大球':[0,0], '小球':[0,0],
         '让球主':[0,0,0], '让球客':[0,0,0]}  # [n, win, push]
    for m in d37:
        for k,v in m.items():
            if k.startswith('1X2'):
                key = '1X2主' if k=='1X2主' else '1X2客'
                s[key][0]+=1
                if v is True: s[key][1]+=1
            elif k.startswith(('大球','小球')):
                key = k.split('(')[0]
                s[key][0]+=1
                if v is True: s[key][1]+=1
            elif k.startswith('让球'):
                key = '让球主' if k.startswith('让球主') else '让球客'
                s[key][0]+=1
                if v is True: s[key][1]+=1
                elif v=='push': s[key][2]+=1
    return s
s37 = stat37()
# 今日4场: Botafogo(1X2平局✗, 小✓, 客+2.5✓) Corinth(客胜✗, 小✓, 客+0.2✗) Kashiwa(客胜✗, 大✓) Tokyo(客胜✗, 大✗)
s37['1X2平'][0]+=1
s37['1X2客'][0]+=3
s37['小球'][0]+=2; s37['小球'][1]+=2
s37['大球'][0]+=2; s37['大球'][1]+=1
s37['让球客'][0]+=2; s37['让球客'][1]+=1

def r(n,w): return ('%.1f%%'%(w/n*100)) if n else '-'
print('== 今日41场精确统计 ==')
for k,(n,w) in [('1X2主',(s37['1X2主'][0],s37['1X2主'][1])), ('1X2客',(s37['1X2客'][0],s37['1X2客'][1])),
                ('大球',(s37['大球'][0],s37['大球'][1])), ('小球',(s37['小球'][0],s37['小球'][1]))]:
    print('%-6s %d/%d = %s' % (k, w, n, r(n,w)))
for k in ('让球主','让球客'):
    n,w,p = s37[k]
    print('%-6s %d/%d 走水%d = %s' % (k, w, n, p, r(n,w)))
print()
print('== 历史(08-15~08-20) ==')
for k in ['1X2-主','1X2-客','大小球-大','大小球-小','让球-主','让球-客']:
    h=hist.get(k,{})
    if h: print('%-8s %d/%d = %s' % (k, h['win'], h['n'], r(h['n'],h['win'])))
print()
print('== 合并总账 ==')
pairs = [('1X2主','1X2-主'), ('1X2客','1X2-客'), ('大球','大小球-大'), ('小球','大小球-小'), ('让球主','让球-主'), ('让球客','让球-客')]
total_rows=[]
for today_key, hist_key in pairs:
    h = hist.get(hist_key,{})
    n,w = s37[today_key][0], s37[today_key][1]
    # 历史让球客的½算半胜, 简化: win计入
    hn, hw = h.get('n',0), h.get('win',0)
    if hist_key=='让球-客' and h.get('half',0): hw += h.get('half',0)*0.5
    tn, tw = hn+n, hw+w
    rate = tw/tn*100 if tn else 0
    total_rows.append((hist_key, hn, hw, n, w, tn, tw, rate))
    print('%-8s 历史 %d/%d + 今日 %d/%d = %d/%d (%.1f%%)' % (hist_key, hw, hn, w, n, tw, tn, rate))
# 1X2合计
h1 = hist['1X2-主']['win']+hist['1X2-客']['win']; h1n = hist['1X2-主']['n']+hist['1X2-客']['n']
t1 = h1 + s37['1X2主'][1]+s37['1X2客'][1]; t1n = h1n + s37['1X2主'][0]+s37['1X2客'][0]+s37['1X2平'][0]
print('1X2合计 历史 %d/%d + 今日 %d/%d = %d/%d (%.1f%%)' % (h1, h1n, s37['1X2主'][1]+s37['1X2客'][1], s37['1X2主'][0]+s37['1X2客'][0]+s37['1X2平'][0], t1, t1n, t1/t1n*100))
