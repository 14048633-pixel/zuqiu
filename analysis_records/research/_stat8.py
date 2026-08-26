# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')
rows = [
 ('02:00','沙超','Al-Fayha','Al-Hilal','0-3'),
 ('03:00','英甲','Sheffield Wednesday','Bradford','0-1'),
 ('03:00','西甲','Rayo Vallecano','Alavés','1-1'),
 ('06:00','南美杯','Olimpia','Vasco da Gama','1-4'),
 ('06:00','南美杯','Macará','Santos','0-0'),
 ('06:00','解放者杯','LDU Quito','Mirassol','0-0'),
 ('06:30','巴乙','Athletic Club','CRB','0-2'),
 ('07:30','巴乙','Novorizontino','América Mineiro','3-0'),
]
n=len(rows)
hw=sum(1 for r in rows if int(r[4][0])>int(r[4][2]))
dr=sum(1 for r in rows if int(r[4][0])==int(r[4][2]))
aw=sum(1 for r in rows if int(r[4][0])<int(r[4][2]))
big=sum(1 for r in rows if int(r[4][0])+int(r[4][2])>2)
sm=sum(1 for r in rows if int(r[4][0])+int(r[4][2])<=2)
goals=sum(int(r[4][0])+int(r[4][2]) for r in rows)
print('总场次:',n)
print('主胜:%d 平:%d 客胜:%d -> 客胜率 %.0f%%'%(hw,dr,aw,aw/n*100))
print('大2.5:%d 小2.5:%d -> 小球率 %.0f%%'%(big,sm,sm/n*100))
print('总进球:%d 场均:%.2f'%(goals,goals/n))
