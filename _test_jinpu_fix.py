import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
os.chdir('D:/ai/电脑庄家/足球竞猜模型训练')
sys.path.insert(0, '.')
sys.path.insert(0, 'src/strategy')
sys.path.insert(0, 'src/rules')
sys.path.insert(0, 'src/features')
from auto_sop import FootballPredictor

raw = """金浦市民 vs 忠北清州
韩国K2联赛
全场数据
类型 盘口 主队(金浦) 客队(忠北清州)
独赢 - 1.77 4.50
让球 -0.5/1 2.03 1.85
大小球 2/2.5 大1.89 小1.97
近10场战绩
金浦市民近10场3胜5平2负不败率80%总进球10总失球11净胜-1主场6场0胜4平2负主场无胜平局泛滥客场4场3胜1平0负客场战力顶尖场均射门15.2次场均射正5.6次场均进球1.0球场均失球1.1球射正转化率17.8%终结效率偏低主场场均仅13.7射4.8射正。。
忠北清州近10场2胜6平2负平局率60%总进球12总失球12客场6场1胜5平0负客场至今不败擅长客场死守拿平局主场4场1胜1平2负场均射门14.7次场均射正5.3次场均进球1.2球场均失球1.2球射正转化率22.6%。。
历史交锋
近7次金浦3胜3平1负2026-05-09金浦1-1清州近4次交手3场小2.5清州最近客场对阵金浦战平近年客场很难输球。
伤病停赛
金浦市民无门将主力后卫中场核心伤停全员健康外援前锋米纳保罗均可首发防线完整无缺。。
忠北清州全队无伤病无红牌停赛门将卢东健主力后卫朴虔佑全部正常出场阵容完整。。
战意对比
金浦市民第8名27分中游无欲区距离升级附加赛区差6分远离降级区主场连续多场无法取胜主场求胜欲望低迷优先保平。。
忠北清州第14名19分仅领先垫底降级区1分随时掉入降级区保级战意极强客场主打死守防守争取客场拿1分保底偷1胜跳出降级圈。。
"""
sop = FootballPredictor()
data = {'status': 'pre_match', 'league': '韩国K2联赛', 'raw_text': raw}
rec = sop.analyze(data)
poi = rec['steps'].get('step8', {}).get('poisson', {})
feats = rec['steps'].get('step2_1', {}).get('features', {})
print('===== 修复后 金浦 vs 忠北清州 =====')
print('特征: home_gf=%s home_ga=%s away_gf=%s away_ga=%s' % (feats.get('home_gf'), feats.get('home_ga'), feats.get('away_gf'), feats.get('away_ga')))
print('λ: 主%s 客%s' % (poi.get('lambda_home'), poi.get('lambda_away')))
print('TOP比分:', poi.get('top5_scores'))
s31 = rec['steps'].get('step31_ev_calc', {})
bb = s31.get('best_bet', {})
print('best_bet:', bb.get('name'), '胜率%.1f%%' % (bb.get('prob',0)*100))
