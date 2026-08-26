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
    name = m.group(1)
    lines = [l for l in sec.split('\n')[1:] if l.startswith(('✅','❌','➖','½'))]
    win = sum(1 for l in lines if l.startswith('✅'))
    half = sum(1 for l in lines if l.startswith('½'))
    hist[name] = dict(n=len(lines), win=win, half=half, rate=win/len(lines)*100 if lines else 0)
# 今日41场
d37 = json.load(open('analysis_records/research/tonight37_review_20260821.json', encoding='utf-8'))
def cnt(prefix):
    n=w=p=0
    for m in d37:
        for k,v in m.items():
            if k.startswith(prefix):
                n+=1
                if v is True: w+=1
                elif v=='push': p+=1
    return n,w,p
x2n,x2w,x2p = cnt('1X2')
oun,ouw,oup = cnt(('小球','大球') if False else 'X') # placeholder
oun=ouw=oup=0
for m in d37:
    for k,v in m.items():
        if k.startswith(('小球','大球')):
            oun+=1
            if v is True: ouw+=1
            elif v=='push': oup+=1
hcn,hcw,hcp = 0,0,0
for m in d37:
    for k,v in m.items():
        if k.startswith('让球'):
            hcn+=1
            if v is True: hcw+=1
            elif v=='push': hcp+=1
# 今日4场
x2n+=4; x2w+=0
oun+=4; ouw+=3
hcn+=2; hcw+=1
# 合并输出
def show(key, hn, hw, tn, tw, label):
    hh = hist.get(key)
    if hh:
        total_n = hh['n'] + tn
        total_w = hh['win'] + tw
        print('%s: 历史 %d/%d (%.1f%%) + 今日 %d/%d = 总 %d/%d (%.1f%%)' % (
            label, hh['win'], hh['n'], hh['rate'], tw, tn, total_w, total_n, total_w/total_n*100 if total_n else 0))
    else:
        print('%s: 今日 %d/%d' % (label, tw, tn))
print('== 合并总账 ==')
# 1X2-主
show('1X2-主', 0,0, 0,0, '1X2-主')
# 直接汇总 1X2 全部(历史主+客)
h1x2_n = hist.get('1X2-主',{}).get('n',0)+hist.get('1X2-客',{}).get('n',0)
h1x2_w = hist.get('1X2-主',{}).get('win',0)+hist.get('1X2-客',{}).get('win',0)
tot_n = h1x2_n + x2n; tot_w = h1x2_w + x2w
print('1X2合计: 历史 %d/%d + 今日 %d/%d = %d/%d (%.1f%%)' % (h1x2_w, h1x2_n, x2w, x2n, tot_w, tot_n, tot_w/tot_n*100 if tot_n else 0))
# OU 大小
for key,label in [('大小球-大','大球'), ('大小球-小','小球')]:
    hh = hist.get(key,{})
    tn = len([1 for m in d37 for k in m if k.startswith(('大球' if '大' in label else '小球'))]) + (3 if '大' in label else 1)
    tw = len([1 for m in d37 for k,v in m.items() if k.startswith(('大球' if '大' in label else '小球')) and v is True]) + (3 if '大' in label else 0)
    total_n = hh.get('n',0)+tn; total_w = hh.get('win',0)+tw
    print('%s: 历史 %d/%d + 今日 %d/%d = %d/%d (%.1f%%)' % (label, hh.get('win',0), hh.get('n',0), tw, tn, total_w, total_n, total_w/total_n*100 if total_n else 0))
# 让球
for key,label in [('让球-主','让球-主'), ('让球-客','让球-客')]:
    hh = hist.get(key,{})
    tn = len([1 for m in d37 for k in m if k.startswith('让球主')]) + 1
    tw = len([1 for m in d37 for k,v in m.items() if k.startswith('让球主') and v is True]) + 1
    total_n = hh.get('n',0)+tn; total_w = hh.get('win',0)+tw
    print('%s: 历史 %d/%d + 今日 %d/%d = %d/%d (%.1f%%)' % (label, hh.get('win',0), hh.get('n',0), tw, tn, total_w, total_n, total_w/total_n*100 if total_n else 0))
