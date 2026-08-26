import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
os.chdir('D:/ai/电脑庄家/足球竞猜模型训练')
sys.path.insert(0, '.')
sys.path.insert(0, 'src/strategy')
sys.path.insert(0, 'src/rules')
sys.path.insert(0, 'src/features')
from auto_sop import FootballPredictor

raw = """水原三星 vs 金海市
韩国K2联赛
全场数据
类型 盘口 主队(水原三星) 客队(金海市)
独赢 - 1.30 8.50
让球 -1.5 1.96 1.92
大小球 2.5/3 大1.89 小1.97
近10场战绩
水原三星近10场4胜3平3负不败率70%主场6场3胜2平1负主场稳定拿分仅1场输球客场4场1胜1平2负客场稳定性偏弱总进球15球总失球13球净胜+2场均进球1.5球场均失球1.3球总射门150次总射正51次场均射门15.0次场均射正5.1次联赛上游水准射正转化率29.4%贴合K2联赛均值主场场均射门16.2次射正5.5次控球率稳定60%阵地压制能力极强。
金海FC近10场2胜3平5负败率50%客场5场1胜2平2负客场擅长死守拿平局主场5场1胜1平4负主场全线崩盘总进球8球总失球20球净胜-12场均进球0.8球场均失球2.0球进攻乏力防线漏洞极大总射门92次总射正33次场均射门9.2次场均射正3.3次联赛垫底水平射正转化率24.2%终结效率低下客场场均射门仅8.7次绝大多数时间被动防守。
历史交锋
本赛季唯一交手2026-03-21金海0-3水原三星半场0-1水原客场完胜零封实力差距断层本场小球格局金海面对水原高压控球完全无力进攻。
伤病停赛
水原三星主力门将金俊浩整套主力后卫线全员健康无防线伤病头号射手外援雷斯6球队内第一得分手中场组织核心朴大元均可首发阵容完整无禁赛人员。
金海FC主力左后卫何耀宗停赛缺席防线关键边路球员缺阵边路防守实力下滑主力门将正常出战两名主力中卫无伤病唯一外援前锋塔泽健康可出场但中场缺少输送孤立无援仅边后卫禁赛。
战意对比
水原三星第1名11胜4平4负积37分直升K1名额区领先第2名首尔衣恋1分手握直升主动权无保级压力主场抢分稳固榜首战意强烈。
金海FC第17名垫底2胜5平12负积11分处在降级区末尾距离安全区足足8分保级形势极其严峻客场主打541死守战术只求拿到平局续命。"""
sop = FootballPredictor()
data = {'status': 'pre_match', 'league': '韩国K2联赛', 'raw_text': raw}
rec = sop.analyze(data)
print('===DONE===')
out = {
  'home': data.get('home'), 'away': data.get('away'),
  'rs': rec.get('agent_risk_signals'),
  'poi': rec['steps'].get('step8', {}).get('poisson'),
  'bb': rec['steps'].get('step31_ev_calc', {}).get('best_bet'),
  'upset': rec.get('upset_assessment', {}).get('level'),
  'agent': (rec.get('agent_tactical', {}) or {}).get('tactical', ''),
  'step31_bets': rec['steps'].get('step31_ev_calc', {}).get('bets')
}
print(json.dumps(out, ensure_ascii=False, indent=1))
