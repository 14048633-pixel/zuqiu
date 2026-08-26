import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
os.chdir('D:/ai/电脑庄家/足球竞猜模型训练')
sys.path.insert(0, '.')
sys.path.insert(0, 'src/strategy')
sys.path.insert(0, 'src/rules')
sys.path.insert(0, 'src/features')
from auto_sop import FootballPredictor

raw = """庆南 vs 大邱FC
韩国K2联赛
全场数据
类型 盘口 主队(庆南) 客队(大邱FC)
独赢 - 3.65 1.89
让球 +0.5 1.99 1.89
大小球 2.5/3 大1.99 小1.87
近10场战绩
庆南FC近10场2胜6平2负不败率80%主场6场4胜2平0负主场长期不败主场拿分能力强悍客场4场0胜4平2负客场无胜绩主打死守平局总进球13球总失球7球净胜+6场均进球1.3球场均失球0.7球联赛上游防守水准总射门146次总射正55次场均射门14.6次场均射正5.5次射正转化率23.6%进攻效率中等依靠稳固防守拿分主场场均射门15.8次射正6.1次阵地压制能力更强。
大邱FC近10场3胜2平5负胜率30%客场5场1胜2平2负客场攻守失衡近期客场连败居多主场5场2胜0平3负总进球16球总失球21球净胜-5场均进球1.6球场均失球2.1球进攻尚可防线漏洞严重总射门153次总射正57次场均射门15.3次场均射正5.7次射正转化率28.1%接近联赛均值但防守漏射过多客场场均失球2.2粒后卫回防速度偏慢。
历史交锋
近5次2026-05-03大邱2-0庆南2019-08-17大邱1-0庆南2019-07-06大邱1-1庆南2019-05-15庆南2-0大邱2019-03-30庆南2-1大邱双方势均力敌近5场交锋仅有2场大2.5交锋偏向小球庆南主场对阵大邱过往不败率75%主场具备克制属性。
伤病停赛
庆南FC主力后卫孙浩俊累计黄牌停赛本场无法登场防线轮换右路防守实力小幅下降主力门将安好真完整待命其余防线球员全部健康头号外援前锋丹雷中场组织核心金夏敏均可首发无门将进攻核心伤缺仅一名后卫停赛。
大邱FC门将整条主力后防线中场核心主力射手全员健康无伤病无红牌停赛无关键球员缺席阵容完整近期丢球过多属于状态问题而非伤病问题。
战意对比
大邱FC第6名9胜5平5负积32分升级附加赛区末位身后华城忠南牙山紧追赢球即可稳固附加赛席位抢分战意强烈无保级压力。
庆南FC第9名6胜7平6负积25分距离升级附加赛区7分追赶难度偏大领先降级区7分完全脱离保级泥潭无欲中游区间战意平淡依托主场不败态势优先保平拿分没有全力强攻必要性。"""
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
