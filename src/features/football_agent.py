"""
足球专业分析Agent - 战术分析 + 情报总结
补充模型算不出的部分: 阵型克制/战意深度/临场判断/爆冷直觉
最终数值仍以模型为准, LLM做定性补充

用法:
    agent = FootballAnalysisAgent()
    result = agent.analyze(match_data, model_result)
"""
import os, json, requests
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DOUBAO_API_KEY = os.getenv('DOUBAO_API_KEY')
DOUBAO_ENDPOINT_ID = os.getenv('DOUBAO_ENDPOINT_ID')
ARK_API_URL = "https://ark.cn-beijing.volces.com/api/v3"


class FootballAnalysisAgent:
    """足球专业分析Agent"""

    def __init__(self, use_doubao: bool = False):
        self.use_doubao = use_doubao
        self.provider = "deepseek"  # 默认DeepSeek, 豆包常超时

    # ============================================================
    # LLM调用
    # ============================================================
    def _llm(self, prompt: str, max_tokens: int = 800) -> str:
        """调用DeepSeek"""
        try:
            headers = {
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": max_tokens
            }
            resp = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers, timeout=60)
            if resp.status_code == 200:
                return resp.json()['choices'][0]['message']['content']
            else:
                print(f"  [DeepSeek错误] {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            print(f"  [LLM调用失败] {e}")
        return ""

    # ============================================================
    # 风险信号提取 (结构化, 用于修正λ)
    # ============================================================
    def risk_signals(self, home_form: str, away_form: str, h2h: str,
                     injuries: str, motivation: str,
                     stats: Optional[Dict] = None) -> Dict:
        """让Agent输出结构化风险信号(0-1), 用于修正λ.
        返回: {
            home_attack_risk: 主队进攻削弱程度,
            away_attack_risk: 客队进攻削弱程度,
            home_defense_risk: 主队防守隐患,
            away_defense_risk: 客队防守隐患,
            deadlock_prob: 死守/闷平概率,
            home_adv_lost: 主队主场优势被剥夺(中立场/停赛等),
            direction: 方向提示(main_team/away_team/draw/unknown)
        }
        """
        stats_txt = ""
        if stats:
            parts = []
            if stats.get('lambda_home') is not None:
                parts.append(f"模型λ: 主{stats['lambda_home']} 客{stats['lambda_away']}")
            if stats.get('over25_prob'):
                parts.append(f"大2.5概率{stats['over25_prob']*100:.0f}%")
            stats_txt = "；".join(parts)

        prompt = f"""你是足球风险分析师。基于情报输出JSON结构化的风险信号(仅输出JSON, 不要其他文字):

【主队】{home_form[:300]}
【客队】{away_form[:300]}
【伤病】{injuries[:200]}
【战意】{motivation[:200]}
【模型】{stats_txt}

评估以下风险(0.0-1.0, 0=无风险 1=极高风险):
- home_attack_risk: 主队进攻被削弱的程度(锋线伤/中立场/进攻哑火)
- away_attack_risk: 客队进攻被削弱程度
- home_defense_risk: 主队防守隐患(防线伤/门将伤)
- away_defense_risk: 客队防守隐患
- deadlock_prob: 双方死守/闷平概率
- home_adv_lost: 主队主场优势被剥夺程度(中立场地/空场/核心停赛)
- direction: 综合指向, 只能是 "home"/"away"/"draw"/"unknown"

输出格式(严格JSON):
{{"home_attack_risk":0.0,"away_attack_risk":0.0,"home_defense_risk":0.0,"away_defense_risk":0.0,"deadlock_prob":0.0,"home_adv_lost":0.0,"direction":"home"}}"""

        result = self._llm(prompt, max_tokens=300)
        # 解析JSON
        import re
        m = re.search(r'\{[^}]*\}', result)
        if m:
            try:
                signals = json.loads(m.group(0))
                # 归一化0-1 + 限幅保护 (防止极端值过度拉偏λ)
                # 上限0.9: 任何单一信号最大影响修正90%→实际限幅
                for k in ['home_attack_risk', 'away_attack_risk', 'home_defense_risk',
                          'away_defense_risk', 'deadlock_prob', 'home_adv_lost']:
                    v = max(0.0, min(1.0, float(signals.get(k, 0))))
                    # 信号限幅: 超过0.85的极端值压到0.85, 防止单一信号主导
                    signals[k] = min(v, 0.85)
                if signals.get('direction') not in ['home', 'away', 'draw', 'unknown']:
                    signals['direction'] = 'unknown'
                return signals
            except Exception:
                return {'home_attack_risk': 0, 'away_attack_risk': 0, 'home_defense_risk': 0,
                        'away_defense_risk': 0, 'deadlock_prob': 0, 'home_adv_lost': 0, 'direction': 'unknown'}
        return {'home_attack_risk': 0, 'away_attack_risk': 0, 'home_defense_risk': 0,
                'away_defense_risk': 0, 'deadlock_prob': 0, 'home_adv_lost': 0, 'direction': 'unknown'}

    # ============================================================
    # 战术分析 (含进球数/射门等定量数据)
    # ============================================================
    def tactical_analysis(self, home_form: str, away_form: str, h2h: str,
                          injuries: str, motivation: str,
                          stats: Optional[Dict] = None) -> Dict:
        """战术+情报深度分析 (LLM定性 + 定量数据参考)"""
        stats_txt = ""
        if stats:
            lines = []
            if stats.get('lambda_home') is not None:
                lines.append(f"模型泊松λ: 主队{stats['lambda_home']} 客队{stats['lambda_away']}")
            if stats.get('top5_scores'):
                scores = [s['score'] for s in stats['top5_scores'][:3]]
                lines.append(f"模型最可能比分: {'、'.join(scores)}")
            if stats.get('home_avg_goals'):
                lines.append(f"主队近10场均进球{stats['home_avg_goals']} 失球{stats['home_avg_ga']}")
            if stats.get('away_avg_goals'):
                lines.append(f"客队近10场均进球{stats['away_avg_goals']} 失球{stats['away_avg_ga']}")
            if stats.get('home_conv'):
                lines.append(f"主队射正转化率{stats['home_conv']}% 客队射正转化率{stats['away_conv']}%")
            if stats.get('over25_prob'):
                lines.append(f"模型大2.5概率{stats['over25_prob']*100:.0f}% 小2.5概率{(1-stats['over25_prob'])*100:.0f}%")
            stats_txt = "\n".join(lines)

        prompt = f"""你是资深足球战术分析师。基于以下比赛情报和模型数据，给出专业分析(不要编造比分/胜率，数值以模型为准):

【主队】
{home_form}
【客队】
{away_form}
【历史交锋】
{h2h}
【伤病停赛】
{injuries}
【战意】
{motivation}

【模型数据参考】
{stats_txt if stats_txt else '无'}

请从以下维度分析，每条不超过50字:
1. 阵型/战术克制关系
2. 关键球员缺阵影响 (结合进球数判断进攻端受影响程度)
3. 战意对比 (谁更想赢)
4. 可能的冷门风险点
5. 比赛节奏预判 (攻防倾向, 结合场均进球判断大小球)
6. 总结: 数据强信号 (一句话, 明确指向主胜/客胜/平局或大球/小球方向)"""

        result = self._llm(prompt, max_tokens=600)
        return {
            "provider": self.provider,
            "tactical": result,
        }

    # ============================================================
    # 结合模型数字, 输出综合报告
    # ============================================================
    def analyze(self, match_data: Dict, model_result: Optional[Dict] = None) -> Dict:
        """完整分析: LLM战术 + 模型数字"""
        home_form = match_data.get('user_form', '')
        away_form = match_data.get('user_form', '')
        # 拆分主客情报
        if '。' in home_form:
            parts = home_form.split('。')
            home_txt = parts[0]
            away_txt = parts[1] if len(parts) > 1 else away_form
        else:
            home_txt = home_form
            away_txt = away_form

        # 构建定量统计数据 (供Agent参考)
        stats = {}
        if model_result:
            stats['lambda_home'] = model_result.get('lambda', {}).get('home')
            stats['lambda_away'] = model_result.get('lambda', {}).get('away')
            stats['top5_scores'] = model_result.get('top5_scores')
            stats['over25_prob'] = model_result.get('over25_prob')
            stats['home_avg_goals'] = model_result.get('home_avg_goals')
            stats['home_avg_ga'] = model_result.get('home_avg_ga')
            stats['away_avg_goals'] = model_result.get('away_avg_goals')
            stats['away_avg_ga'] = model_result.get('away_avg_ga')
            stats['home_conv'] = model_result.get('home_conv')
            stats['away_conv'] = model_result.get('away_conv')

        report = {
            "match": match_data.get('home', '') + " vs " + match_data.get('away', ''),
            "model_result": model_result,
            "tactical": self.tactical_analysis(
                home_txt, away_txt,
                match_data.get('user_h2h', ''),
                match_data.get('user_injuries', ''),
                match_data.get('user_motivation', ''),
                stats,
            ),
        }
        return report

    def format_report(self, report: Dict) -> str:
        """格式化报告"""
        lines = []
        lines.append("=" * 70)
        lines.append(f"  ⚽ 足球专业分析报告")
        lines.append(f"  {report['match']}")
        lines.append("=" * 70)

        if report.get('model_result'):
            mr = report['model_result']
            lines.append(f"\n【模型计算】(权威)")
            if 'best_bet' in mr:
                lines.append(f"  最优投注: {mr['best_bet']}")
            if 'lambda' in mr:
                lam = mr['lambda']
                lines.append(f"  泊松λ: 主{lam.get('home','?')} 客{lam.get('away','?')}")

        tactical = report.get('tactical', {})
        if tactical.get('tactical'):
            lines.append(f"\n【LLM战术分析】(参考, 用{tactical.get('provider','?')})")
            lines.append(tactical['tactical'])

        lines.append(f"\n{'='*70}")
        lines.append("  结论: 数值以模型为准, LLM分析仅供战术参考")
        return "\n".join(lines)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    agent = FootballAnalysisAgent()
    test = {
        "home": "上海海港B队",
        "away": "山西崇德荣海",
        "user_form": "上海海港B队冲甲强队北区榜首近10场6胜2平2负场均进2.2失1.1。山西崇德荣海冲甲竞争北区第3近10场7胜2平1负场均进2.1失0.8近期5连胜缺主力前锋。",
        "user_h2h": "3次交锋海港B2胜1平不败",
        "user_injuries": "山西主力前锋丁云峰停赛, 海港B全员健康",
        "user_motivation": "海港B保榜首, 山西冲甲需追分",
    }
    report = agent.analyze(test, {"best_bet": "小2.25@1.73", "lambda": {"home": 0.57, "away": 0.75}})
    print(agent.format_report(report))
