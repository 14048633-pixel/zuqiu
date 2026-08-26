"""
足球数据收集系统 - 收集特定赔率结构的比赛数据
用于验证"强队+深盘→大球"策略
"""
import os
import json
from datetime import datetime

DATA_DIR = "strategy_data"
os.makedirs(DATA_DIR, exist_ok=True)

# 策略条件
STRATEGY_CONDITIONS = {
    "name": "强队深盘大球策略",
    "description": "主胜<1.20 + 让球>-2 → 追大球",
    "rules": {
        "odds_home_max": 1.20,  # 主胜赔率上限
        "handicap_min": -2,      # 让球盘口下限 (如-2/2.5取-2)
    }
}

# 数据文件
DATA_FILES = [
    f"{DATA_DIR}/strong_team_deep_handicap.json",
    f"{DATA_DIR}/normal_handicap.json"
]


class DataCollector:
    def __init__(self):
        self.data = self._load_data()
        self._update_stats()

    def _load_data(self):
        """加载历史数据 (记录每场来源文件)"""
        all_matches = []
        for data_file in DATA_FILES:
            if os.path.exists(data_file):
                with open(data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    matches = data.get('matches', [])
                    print(f"  从 {data_file} 加载了 {len(matches)} 场比赛")
                    for m in matches:
                        print(f"    - {m.get('match', 'N/A')}: {m.get('hdp_result', 'N/A')}")
                        m['_source'] = data_file
                        all_matches.append(m)
        return {"matches": all_matches, "stats": {}}

    def _save_data(self):
        """保存数据 (按来源文件写回)"""
        # 按来源文件分组
        grouped = {f: [] for f in DATA_FILES}
        for m in self.data['matches']:
            src = m.get('_source', DATA_FILES[0])
            # 去掉内部标记
            m_copy = dict(m)
            m_copy.pop('_source', None)
            grouped[src].append(m_copy)

        for data_file, matches in grouped.items():
            with open(data_file, 'w', encoding='utf-8') as f:
                json.dump({"matches": matches, "stats": {}}, f, ensure_ascii=False, indent=2)

    def add_match(self, match_data, result_data, real_data=None):
        """添加一场比赛数据 (自动去重)"""
        match_key = f"{match_data['home']} vs {match_data['away']}"

        # 去重: 同一场次已存在则更新，否则新增
        existing = None
        for m in self.data['matches']:
            if m.get('match') == match_key:
                existing = m
                break

        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "match": match_key,
            "home": match_data.get('home', match_data['home']),
            "away": match_data.get('away', match_data['away']),
            "home_en": match_data.get('home_en', ''),
            "away_en": match_data.get('away_en', ''),
            "league": match_data['league'],
            "odds_home": float(match_data['odds_home']),
            "odds_draw": float(match_data['odds_draw']),
            "odds_away": float(match_data['odds_away']),
            "hdp_home": match_data['hdp_home'],
            "hdp_away": match_data['hdp_away'],
            "ou_over": match_data['ou_over'],
            "ou_under": match_data['ou_under'],
            "final_score": result_data.get('final_score', 'N/A'),
            "total_goals": result_data.get('total_goals', 0),
            "hdp_result": result_data.get('hdp_result', 'N/A'),
            "ou_result": result_data.get('ou_result', 'N/A'),
            "prediction": result_data.get('prediction', 'N/A'),
            "confidence": result_data.get('confidence', 'N/A'),
            "conditions_met": self._check_conditions(match_data)
        }

        if existing:
            # 更新已有记录
            existing.update(record)
            print(f"  已更新(去重): {match_key}")
        else:
            # 新增记录
            self.data['matches'].append(record)
            print(f"  已记录: {match_key} ({record['final_score']})")

        # 添加真实数据（用户提供的）
        if real_data:
            record['real_data'] = {
                'home_form': real_data.get('home_form', ''),
                'away_form': real_data.get('away_form', ''),
                'h2h': real_data.get('h2h', ''),
                'injuries': real_data.get('injuries', ''),
                'motivation': real_data.get('motivation', ''),
                'analysis': real_data.get('analysis', '')
            }

        self._update_stats()
        self._save_data()

        return record

    def _check_conditions(self, match_data):
        """检查是否满足策略条件"""
        odds_home = float(match_data['odds_home'])
        hdp_str = match_data['hdp_home']

        # 解析让球数
        try:
            if '/' in hdp_str:
                # 处理 -2/2.5 @1.82 格式 (让球范围)
                parts = hdp_str.split('/')
                num1_str = parts[0].replace('@', '').strip().replace('+', '')
                num2_str = parts[1].split('@')[0].strip()
                num1 = float(num1_str)
                num2 = float(num2_str)
                # 如果第一个是负数，第二个是正数，取负数平均值
                if num1 < 0 and num2 > 0:
                    hdp_value = (num1 + (-num2)) / 2  # 如 -2 和 -2.5 平均
                else:
                    hdp_value = (num1 + num2) / 2
            else:
                # 处理 -2 @1.82 格式
                hdp_value = float(hdp_str.split('@')[0].strip().replace('+', ''))
        except Exception as e:
            print(f"  [警告] 无法解析让球盘口: {hdp_str}, 错误: {e}")
            hdp_value = 0

        # 检查条件
        odds_met = odds_home <= STRATEGY_CONDITIONS['rules']['odds_home_max']
        hdp_met = hdp_value <= STRATEGY_CONDITIONS['rules']['handicap_min']

        return {
            "odds_home_met": odds_met,
            "hdp_met": hdp_met,
            "both_met": odds_met and hdp_met,
            "hdp_value": hdp_value
        }

    def _update_stats(self):
        """更新统计数据"""
        matches = self.data['matches']
        if not matches:
            return

        # 统计所有比赛
        total = len(matches)

        # 统计满足强队深盘条件的比赛
        qualified = [m for m in matches if m.get('conditions_met', {}).get('both_met', False)]

        # 统计大球率 (所有比赛)
        over_count = sum(1 for m in matches if m.get('ou_result') == '大球')
        over_rate = over_count / total if total > 0 else 0

        # 统计让球胜率 (所有比赛)
        hdp_win_count = sum(1 for m in matches if m.get('hdp_result') == '让负')
        hdp_win_rate = hdp_win_count / total if total > 0 else 0

        # 统计平均进球
        avg_goals = sum(m.get('total_goals', 0) for m in matches) / total if total > 0 else 0

        self.data['stats'] = {
            "total": total,
            "qualified": len(qualified),
            "over_count": over_count,
            "over_rate": round(over_rate * 100, 1),
            "hdp_win_count": hdp_win_count,
            "hdp_win_rate": round(hdp_win_rate * 100, 1),
            "avg_goals": round(avg_goals, 2)
        }

    def get_analysis(self):
        """获取数据分析"""
        stats = self.data['stats']

        if stats.get('qualified', 0) < 10:
            return {
                "status": "数据不足",
                "message": f"需要至少10场数据，当前只有{stats.get('qualified', 0)}场",
                "stats": stats
            }

        analysis = {
            "status": "可分析",
            "recommendation": "",
            "stats": stats
        }

        # 判断策略是否有效
        if stats['over_rate'] >= 60:
            analysis['recommendation'] = f"大球策略有效 (大球率{stats['over_rate']}%)"
            analysis['strategy'] = "追大球"
        elif stats['over_rate'] <= 40:
            analysis['recommendation'] = f"大球策略无效 (大球率{stats['over_rate']}%)"
            analysis['strategy'] = "追小球"
        else:
            analysis['recommendation'] = f"大球率中性 ({stats['over_rate']}%)"
            analysis['strategy'] = "观望"

        return analysis

    def print_stats(self):
        """打印统计数据"""
        analysis = self.get_analysis()
        stats = analysis['stats']

        print("\n" + "=" * 70)
        print("  策略数据统计")
        print("=" * 70)
        print(f"  总场次: {stats.get('total', 0)}")
        print(f"  满足强队深盘条件: {stats.get('qualified', 0)}")
        print(f"  大球次数: {stats.get('over_count', 0)}")
        print(f"  大球率: {stats.get('over_rate', 0)}%")
        print(f"  让负次数: {stats.get('hdp_win_count', 0)}")
        print(f"  让负率: {stats.get('hdp_win_rate', 0)}%")
        print(f"  平均进球: {stats.get('avg_goals', 0)}")
        print(f"\n  结论: {analysis.get('recommendation', '数据不足')}")
        print("=" * 70)


def main():
    import sys

    collector = DataCollector()

    if len(sys.argv) > 1 and sys.argv[1] == '--stats':
        collector.print_stats()
        return

    # 测试添加一场数据
    match = {
        'home': '奥克兰城',
        'away': '奥林匹克湾',
        'league': '新西兰北部联赛',
        'odds_home': '1.11',
        'odds_draw': '7.30',
        'odds_away': '11.5',
        'hdp_home': '-2/2.5 @1.82',
        'hdp_away': '+2/2.5 @1.96',
        'ou_over': '3.5/4 @1.81',
        'ou_under': '3.5/4 @1.97'
    }

    result = {
        'final_score': '3-0 (半场)',
        'total_goals': 3,
        'hdp_result': '待定',
        'ou_result': '大球 (已进3球，超过3.5)'
    }

    collector.add_match(match, result)
    collector.print_stats()


if __name__ == "__main__":
    main()
