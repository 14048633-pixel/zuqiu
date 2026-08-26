import sys, os
sys.stdout.reconfigure(encoding='utf-8')
os.chdir('D:/ai/电脑庄家/足球竞猜模型训练')
sys.path.insert(0, 'src/features')
from data_extractor import MatchDataExtractor
e = MatchDataExtractor()

raw = """金浦 vs 忠北清州
韩国K2联赛
全场数据
类型 盘口 主队(金浦) 客队(忠北清州)
独赢 - 1.77 4.50
让球 -0.5/1 2.03 1.85
大小球 2/2.5 大1.89 小1.97
让球盘口细分
-0.5 1.77 +0.5 2.12
-0.5 2.47 +0.5 1.56
-1 2.42 +1 1.58
0 1.43 0 2.81
大小球细分
大2.5 2.16 小2.5 1.72
大0.5/1 1.64 小0.5/1 2.28
大2 1.61 小2 2.33
大1/1.5 2.53 小1/1.5 1.51"""
d = e.extract(raw)
print('=== Step 0.5 数据提取 ===')
print('主队:', d.get('home_team'), '| 客队:', d.get('away_team'))
print('独赢: 主%s 平%s 客%s' % (d.get('odds_home'), d.get('odds_draw'), d.get('odds_away')))
print('让球: %s | %s' % (d.get('hdp_home'), d.get('hdp_away')))
print('大小: %s | %s' % (d.get('ou_over'), d.get('ou_under')))
print('主客确认:', d.get('home_away_confirmed'))
