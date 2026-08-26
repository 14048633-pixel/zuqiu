import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
os.chdir('D:/ai/电脑庄家/足球竞猜模型训练')
sys.path.insert(0, '.')
sys.path.insert(0, 'src/strategy')
sys.path.insert(0, 'src/rules')
sys.path.insert(0, 'src/features')
from auto_sop import FootballPredictor

raw = """乔治罗尼亚 vs 流浪者
欧联资格赛
全场数据
类型 盘口 主队(乔治罗尼亚) 客队(流浪者)
独赢 - 2.64 2.27
让球 +0/0.5 1.75 2.07
大小球 2.5/3 大1.99 小1.87
近10场战绩
乔治罗尼亚近10场总射门155次射正59次总进球16球总失球7球场均射门15.5次场均射正5.9次场均进球1.6球场均失球0.7球主场近10个7胜3平0负主场零输球6场零封射正转化率27.1%。
流浪者近10场总射门165次射正63次总进球25球总失球13球场均射门16.5次场均射正6.3次场均进球2.5球场均失球1.3球客场近10个4胜2平4负客场胜率40%易客场崩盘射正转化率39.7%。
历史交锋
两队无任何正式交手记录首次遭遇战。
伤病停赛
乔治罗尼亚主力左边锋约兹维亚克肌肉拉伤缺阵门将双主力中卫后腰中轴线全健康防线无隐患。
流浪者主力中卫戈弗雷腿筋伤缺4周仅剩1名健康正印中卫后腰西富恩特斯报销主力中场拉斯金休战。
战意对比
乔治罗尼亚波超卫冕冠军前2轮全胜欧联优先级大于联赛主场全主力高压逼抢抢首回合优势。
流浪者苏超豪门联赛约等于欧联客场541收缩死守求平局偷客场进球留力次回合。"""
sop = FootballPredictor()
data = {'status': 'pre_match', 'league': '欧联资格赛', 'raw_text': raw}
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
