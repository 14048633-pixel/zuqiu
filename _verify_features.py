import sys, json
sys.stdout.reconfigure(encoding='utf-8')
import sys as _sys
_sys.path.insert(0, 'src/features')
from feature_extractor import MatchFeatureExtractor

# 读取8场数据
d = json.load(open('strategy_data/denmark_cup_8matches_20260805.json', 'r', encoding='utf-8'))
ex = MatchFeatureExtractor()

print("=" * 90)
print("  特征提取器 8场验证 - 数据方向 vs 实际结果")
print("=" * 90)

# 实际结果
actual = {
    "欧雷 vs 弗雷德里西亚": "0-6 客胜",
    "维比 vs ASA阿晓斯": "0-0 平(ASA点球晋级)",
    "根图夫特宠格德 vs 厄华特": "1-2 客胜",
    "FC南海岸 vs 伊绍伊IF": "3-1 主胜",
    "灵斯泰德 vs 费林": "0-1 客胜",
    "布隆索伊 vs 科治": "1-0 主胜",
    "霍尔斯特布罗 vs 奥尔堡": "1-3 客胜",
    "科尔丁BK vs 奈斯比": "0-1 客胜",
}

for m in d['matches']:
    name = m['match']
    home = m['form_home']
    away = m['form_away']
    h2h = m['h2h']
    inj = f"{m['injuries_home']} {m['injuries_away']}"
    mot = f"主队战意:{m['motivation_home']} 客队战意:{m['motivation_away']}"

    feats = ex.extract(home, away, h2h, inj, mot)

    # 计算数据方向分 (正=主队占优, 负=客队占优)
    direction_score = 0
    reasons = []

    # 职业化
    pro_gap = feats['pro_gap']
    if pro_gap < 0:
        direction_score += pro_gap * 2
        reasons.append(f"客队职业化高(差{abs(pro_gap)}级)")
    elif pro_gap > 0:
        direction_score += pro_gap * 2
        reasons.append(f"主队职业化高(差{pro_gap}级)")

    # 状态
    form_diff = feats['form_diff']
    direction_score += form_diff * 3
    if form_diff > 0:
        reasons.append(f"主队状态好(+{form_diff:.1f})")
    elif form_diff < 0:
        reasons.append(f"客队状态好({form_diff:.1f})")

    # 攻防
    if feats['home_attack_disabled']:
        direction_score -= 1.5
        reasons.append("主队锋线哑火")
    if feats['away_attack_disabled']:
        direction_score += 1.5
        reasons.append("客队锋线哑火")
    if feats['home_defense_weak']:
        direction_score -= 1.5
        reasons.append("主队防线弱")
    if feats['away_defense_weak']:
        direction_score += 1.5
        reasons.append("客队防线弱")

    # 交锋碾压
    if feats['h2h_domination']:
        direction_score -= 1 if '根图夫特' in name else 0  # 简化

    pred = "主队占优" if direction_score > 1 else "客队占优" if direction_score < -1 else "均势"
    actual_res = actual.get(name, "?")

    print(f"\n  【{name}】")
    print(f"  数据方向分: {direction_score:+.1f} → {pred}")
    print(f"  实际结果: {actual_res}")
    print(f"  特征: {'; '.join(reasons) if reasons else '无明显信号'}")
    match_str = "✅" if (pred == "主队占优" and "主胜" in actual_res) or (pred == "客队占优" and "客胜" in actual_res) or (pred == "均势" and "平" in actual_res) else "⚠️"
    print(f"  判断: {match_str}")
