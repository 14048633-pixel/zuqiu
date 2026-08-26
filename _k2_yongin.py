import sys, os, json
sys.stdout.reconfigure(encoding='utf-8')
os.chdir('D:/ai/电脑庄家/足球竞猜模型训练')
sys.path.insert(0, '.')
sys.path.insert(0, 'src/strategy')
sys.path.insert(0, 'src/rules')
sys.path.insert(0, 'src/features')
from auto_sop import FootballPredictor

raw = """龙仁 vs 釜山偶像
韩国K2联赛
全场数据
类型 盘口 主队(龙仁) 客队(釜山偶像)
独赢 - 3.85 1.90
让球 +0.5 1.98 1.90
大小球 2.5 大2.03 小1.83
近10场战绩
龙仁FC近10场1胜7平2负平局率70%联赛平局最多的队伍之一主场6场1胜3平2负主场拿分基本靠平局取胜能力极差客场4场0胜4平0负客场至今不败死守拿平能力突出总进球12球总失球16球净胜-4场均进球1.2球场均失球1.6球进攻乏力防守漏洞较多总射门92次总射正32次场均射门9.2次场均射正3.2次射门射正数据联赛下游射正转化率26.1%终结效率偏低主场场均射门仅8.8次主动攻坚意愿弱习惯收缩防守。
釜山偶像近10场4胜2平4负状态起伏明显近期遭遇连败客场5场2胜1平2负客场胜率一般连续丢球增多主场5场2胜1平3负主场强势不再接连输球总进球22球总失球19球净胜+3场均进球2.2球场均失球1.9球进攻火力上游但近期防线频繁崩盘总射门156次总射正57次场均射门15.6次场均射正5.7次射正转化率38.6%进攻效率远超联赛均值客场下半场容易体能下滑近3个客场场均丢2球。
历史交锋
近3次2026-04-11釜山2-0龙仁半场0-0下半场连入两球零封2025-10-22龙仁1-1釜山2025-07-13釜山2-1龙仁近3次交手釜山2胜1平保持不败心理压制龙仁3场对决2场小2.5交锋偏向沉闷龙仁主场面对釜山近1次握手言和具备死守逼平能力。
伤病停赛
龙仁FC主力门将完整在岗后防线全员健康无伤病中场球员林采玟累计6黄本场遭遇停赛中场拦截主力缺席中场硬度下降头号射手蒂格劳助攻核心金甫燮均可首发进攻体系完整无门将后卫前锋核心伤缺仅中场拦截手禁赛。
釜山偶像主力门将整条后防线无伤病停赛外援进攻核心里克尔梅7球5助攻队内头号大腿健康可出战中场哈维尔身背4张黄牌本场谨慎防守避免停赛不会冒险上抢无主力门将防线核心射手缺阵阵容完整近期丢球过多为状态起伏所致。
战意对比
釜山偶像第3名11胜3平5负积36分与第2首尔衣恋同分仅落后榜首水原三星1分身处直升争夺战区间身后华城大邱紧追必须抢分守住直升席位抢分战意极强无保级压力。
龙仁FC第13名3胜10平6负积19分处于降级边缘仅领先垫底金海8分领先降级区安全线1分保级压力巨大球队擅长平局拿分主场优先死守保1分绝不主动强攻。"""
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
