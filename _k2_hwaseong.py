import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
os.chdir('D:/ai/电脑庄家/足球竞猜模型训练')
sys.path.insert(0, '.')
sys.path.insert(0, 'src/strategy')
sys.path.insert(0, 'src/rules')
sys.path.insert(0, 'src/features')
from auto_sop import FootballPredictor

raw = """华城 vs 首尔衣恋
韩国K2联赛
全场数据
类型 盘口 主队(华城) 客队(首尔衣恋)
独赢 - 2.79 2.21
让球 +0/0.5 1.87 2.01
大小球 2.5/3 大1.95 小1.91
近10场战绩
华城FC近10场7胜1平2负不败率80%主场6场5胜1平0负主场保持不败主场战力联赛顶尖客场4场2胜0平2负总进球24球总失球12球净胜+12场均进球2.4球场均失球1.2球总射门168次总射正65次场均射门16.8次场均射正6.5次射正转化率36.9%远超联赛均值主场场均射门17.7次射正6.9次攻坚能力极强。
首尔衣恋近10场6胜2平2负不败率80%客场5场3胜1平1负客场抢分能力强劲主场5场3胜1平1负总进球22球总失球14球净胜+8场均进球2.2球场均失球1.4球总射门161次总射正62次场均射门16.1次场均射正6.2次射正转化率35.5%进攻效率联赛上游。
历史交锋
近5次2026-04-26首尔衣恋1-2华城2025-10-07首尔1-1华城2025-08-10首尔0-0华城2025-05-24华城0-1首尔2024-09-14华城2-1首尔两队实力接近5次交手分出胜负3场平局2场近2次碰面1场分胜负1场平局小球居多5场对决3场小2.5华城主场对阵首尔衣恋胜率50%没有明显主场压制优势。
伤病停赛
华城FC主力门将金承建整套主力防线全员健康无后卫伤停进攻核心外援前锋德米特留斯中场组织核心崔明熙均可首发阵容完整无伤病停赛。
首尔衣恋主力门将状态完好主力中卫组合全部正常出战左边锋外援欧勒长期伤缺边路爆点缺失属于唯一伤病中场核心加布里埃尔头号射手金承俊正常登场防线无缺损无红牌停赛。
战意对比
首尔衣恋第2名11胜3平5负积36分直升K1区域距离榜首水原三星仅1分全力争夺前2直升名额抢分战意拉满无保级压力客场只求拿分抢榜首位置。
华城FC第4名10胜4平5负积34分升级附加赛区距离直升区只差2分主场不败属性极强具备冲击直升区机会领先降级区13分无保级压力主场全力争胜冲排名。"""
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
