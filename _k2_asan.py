import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
os.chdir('D:/ai/电脑庄家/足球竞猜模型训练')
sys.path.insert(0, '.')
sys.path.insert(0, 'src/strategy')
sys.path.insert(0, 'src/rules')
sys.path.insert(0, 'src/features')
from auto_sop import FootballPredictor

raw = """忠南牙山 vs 安山绿人
韩国K2联赛
全场数据
类型 盘口 主队(忠南牙山) 客队(安山绿人)
独赢 - 1.59 4.85
让球 -1 2.04 1.84
大小球 2.5 大1.83 小2.03
近10场战绩
忠南牙山近10场4胜3平3负不败率70%总进球15总失球11净胜+4主场6场3胜2平1负主场胜率50%近期主场两连胜连续零封城南始兴市民客场4场1胜1平2负场均射门15.7次场均射正5.8次场均进球1.5球场均失球1.1球射正转化率25.9%主场场均射正6.2次攻坚效率明显高于客场。
安山绿人近10场2胜1平7负败率70%总进球10总失球17净胜-7客场5场1胜1平3负客场防守崩盘场均失球1.8粒主场5场1胜0平4负场均射门14.2次场均射正4.9次场均进球1.0球场均失球1.7球射正转化率20.4%客场场均仅4.3次射正很难制造威胁。
历史交锋
近6次忠南牙山5胜1平未尝败绩2026-04-05安山1-3牙山近6次对决5场小2.5牙山主场对阵安山连续3场零封。
伤病停赛
忠南牙山无门将主力后卫中场核心伤停无红牌停赛主力防线完整外援前锋丹尼森席尔瓦队内头号射手中场组织核心孙准浩均可首发全员健康。
安山绿人门将赵晟训正常出场后卫姜东铉外援中卫哈泽尔轻微肌肉不适进替补名单大概率不首发防线实力小幅下降无绝对核心重伤缺阵近期防线连续崩盘属状态下滑。
战意对比
忠南牙山第7名27分距离升级附加赛区第6名大邱FC仅5分仍有冲击升级附加赛希望战意中等偏上坐拥主场连胜势头抢分冲击上游梯队远离降级区无保级压力。
安山绿人第15名18分仅领先垫底降级区1分随时跌入降级区客场防守漏洞巨大抢分难度极高战意极强保级战意但球队状态极差客场攻坚乏力优先死守保平局。"""
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
