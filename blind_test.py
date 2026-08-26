"""
盲测脚本 - 验证 Agent 带进球数后方向判断是否准确
==================================================
用3场真实历史比赛, 但隐藏队名和赛果, 只给数据特征.
判断 Agent 的方向结论与真实赛果是否一致.
"""
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src', 'features'))
from football_agent import FootballAnalysisAgent


def run_blind(name, home_form, away_form, stats):
    """盲测单场"""
    print("=" * 70)
    print(f"盲测场次: {name}")
    print(f"【模型数据】λ 主{stats['lambda_home']} 客{stats['lambda_away']} | "
          f"大2.5概率{stats['over25_prob']*100:.0f}%")
    print(f"场均进球: 甲{stats['home_avg_goals']}(失{stats['home_avg_ga']}) "
          f"乙{stats['away_avg_goals']}(失{stats['away_avg_ga']}) | "
          f"转化率: 甲{stats['home_conv']}% 乙{stats['away_conv']}%")
    print()
    agent = FootballAnalysisAgent()
    r = agent.tactical_analysis(home_form, away_form, "无交手记录",
                                stats.get('injuries', ''), stats.get('motivation', ''),
                                stats)
    print("【Agent判断】")
    print(r.get('tactical', '空'))
    print()


def main():
    # 比赛1: 甲=古比斯(主) 乙=克拉约瓦(客) [真实1-1]
    run_blind(
        "盲测1 (主队vs客队)",
        "甲队近10场总射门150次总进球17球总失球6球场均射门15.0次场均进球1.7球场均失球0.6球射正转化率29.8%主场近10个6胜3平1负不败率90%但欧战主场连续3场被零封。",
        "乙队近10场总射门155次总进球21球总失球11球场均射门15.5次场均进球2.1球场均失球1.1球射正转化率36.8%客场近6场1胜3平2负客场胜率仅17%客场1-5惨败。",
        {'lambda_home': 1.8, 'lambda_away': 1.1, 'over25_prob': 0.554,
         'home_avg_goals': 1.7, 'home_avg_ga': 0.6, 'away_avg_goals': 2.1, 'away_avg_ga': 1.1,
         'home_conv': 29.8, 'away_conv': 36.8,
         'injuries': '甲队中场核心停赛2中场伤缺防线健康。乙队主力门将中卫伤停防线重创。',
         'motivation': '甲队欧联优先级大于联赛全力争正赛。乙队客场只求客场进球留力次回合。'}
    )

    # 比赛2: 甲=乔治罗尼亚(主) 乙=流浪者(客) [真实2-1]
    run_blind(
        "盲测2 (主队vs客队)",
        "甲队近10场总射门155次总进球16球总失球7球场均射门15.5次场均进球1.6球场均失球0.7球主场近10个7胜3平0负主场零输球6场零封。",
        "乙队近10场总射门165次总进球25球总失球13球场均射门16.5次场均进球2.5球场均失球1.3球客场近10个4胜2平4负客场胜率40%易客场崩盘。",
        {'lambda_home': 1.64, 'lambda_away': 1.26, 'over25_prob': 0.554,
         'home_avg_goals': 1.6, 'home_avg_ga': 0.7, 'away_avg_goals': 2.5, 'away_avg_ga': 1.3,
         'home_conv': 27.1, 'away_conv': 39.7,
         'injuries': '甲队主力左边锋缺阵防线健康。乙队主力中卫伤缺4周仅剩1名健康中卫后腰报销。',
         'motivation': '甲队欧联优先级大于联赛主场全力抢首回合优势。乙队客场541收缩死守求平局留力次回合。'}
    )

    # 比赛3: 甲=特拉维夫(主) 乙=索菲亚(客) [真实0-3]
    run_blind(
        "盲测3 (主队vs客队)",
        "甲队近10场总射门138次总进球21球总失球9球场均射门13.8次场均进球2.1球场均失球0.9球射正转化率38.9%主场胜率70%但本场改格鲁吉亚中立场地失去主场优势主力左后卫停赛外援前锋重伤。",
        "乙队近10场总射门157次总进球18球总失球8球场均射门15.7次场均进球1.8球场均失球0.8球射正转化率30.5%客场胜率仅20%擅长死守平局上两轮欧联客场全部零封对手。",
        {'lambda_home': 1.48, 'lambda_away': 1.42, 'over25_prob': 0.554,
         'home_avg_goals': 2.1, 'home_avg_ga': 0.9, 'away_avg_goals': 1.8, 'away_avg_ga': 0.8,
         'home_conv': 38.9, 'away_conv': 30.5,
         'injuries': '甲队主力左后卫停赛外援前锋重伤门将中卫健康。乙队全员健康无伤病阵容完整。',
         'motivation': '甲队欧联优先级高全力拿首回合但中立场地稳中求胜。乙队客场死守平局拿到客场进球即完成任务。'}
    )


if __name__ == "__main__":
    main()
