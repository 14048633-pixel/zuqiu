"""
投注校验模块 v1.0
===================
防止"湖北青年星事件"重演的两层防线:
  第2层: 投注生成校验 - 投注单每条腿必须等于该场best_bet(最高胜率腿), 否则拦下
  第3层: 结算复盘校验 - 结算后自动比对"实际选腿 vs best_bet", 不一致标记执行失误

用法:
  from bet_validator import BetValidator
  v = BetValidator()

  # 第2层: 生成投注前校验
  ok, errors = v.verify_bet_legs(legs, best_bets_map)
  # legs = [{"match": "湖北 vs 江西", "bet": "主队+0/0.5"}, ...]
  # best_bets_map = {"湖北 vs 江西": {"name": "小2.25", "prob": 0.8525, ...}}

  # 第3层: 结算后复盘
  v.record_settlement(legs, results, best_bets_map)
"""
import json
import os
from datetime import datetime


class BetValidator:
    """投注校验 + 复盘"""

    DATA_DIR = "strategy_data"
    REVIEW_FILE = f"{DATA_DIR}/bet_execution_review.json"

    def __init__(self, data_dir=None):
        if data_dir:
            self.DATA_DIR = data_dir
            self.REVIEW_FILE = f"{data_dir}/bet_execution_review.json"
        os.makedirs(self.DATA_DIR, exist_ok=True)
        self.review_data = self._load_review()

    def _load_review(self):
        if os.path.exists(self.REVIEW_FILE):
            try:
                with open(self.REVIEW_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {"records": [], "stats": {}}
        return {"records": [], "stats": {}}

    def _save_review(self):
        # 汇总统计
        recs = self.review_data['records']
        total_legs = sum(len(r.get('legs', [])) for r in recs)
        exec_errors = sum(1 for r in recs if r.get('execution_error'))
        self.review_data['stats'] = {
            "total_bets": len(recs),
            "total_legs": total_legs,
            "execution_errors": exec_errors,
            "execution_error_rate": round(exec_errors / max(total_legs, 1), 4)
        }
        with open(self.REVIEW_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.review_data, f, ensure_ascii=False, indent=2)

    # ============================================================
    # 第2层: 投注生成校验
    # ============================================================
    def verify_bet_legs(self, legs, best_bets_map, combo_type="串关"):
        """
        校验投注单每条腿是否等于该场best_bet(最高胜率腿).
        legs: [{"match": "湖北 vs 江西", "bet": "主队+0/0.5", "odds": 1.7}, ...]
        best_bets_map: {"湖北 vs 江西": {"name": "小2.25", "prob": 0.8525, "odds": 1.72, "ev": 0.466}, ...}
        返回: (ok, errors, warnings)
          - ok: 是否全部通过
          - errors: 硬错误列表 (选腿 != best_bet, 必须拦截)
          - warnings: 软警告列表
        """
        errors = []
        warnings = []

        for leg in legs:
            match = leg.get('match', '')
            bet = leg.get('bet', '')
            bb = best_bets_map.get(match)

            if not bb:
                warnings.append(f"{match}: 没有best_bet记录, 无法校验")
                continue

            bb_name = bb.get('name', '')
            # 归一化比较: 去除空白/单位差异
            if not self._bet_equal(bet, bb_name):
                errors.append(
                    f"{match}: 选腿[{bet}] ≠ best_bet[{bb_name}] "
                    f"(最高胜率腿, 胜率{bb.get('prob', 0):.1%}) → 违反串关胜率优先规则, 已拦截"
                )
            else:
                warnings.append(
                    f"{match}: ✓ 选腿[{bet}] = best_bet[{bb_name}] (胜率{bb.get('prob', 0):.1%}, EV{bb.get('ev', 0):+.1%})"
                )

        ok = len(errors) == 0
        return ok, errors, warnings

    @staticmethod
    def _bet_equal(bet_a, bet_b):
        """归一化比较两条腿是否相同 (忽略小写/空格/@赔率)"""
        def norm(s):
            s = s.lower().replace(' ', '')
            if '@' in s:
                s = s.split('@')[0]
            return s
        return norm(bet_a) == norm(bet_b)

    # ============================================================
    # 第3层: 结算复盘校验
    # ============================================================
    def record_settlement(self, combo_type, stake, legs, best_bets_map, results_map, pnl):
        """
        结算后记录并比对实际选腿 vs best_bet.
        legs: [{"match":..., "bet":..., "odds":..., "prob":..., "score":..., "leg_result":...}]
        best_bets_map: {"湖北 vs 江西": {"name": "小2.25", ...}}
        results_map: {"湖北 vs 江西": {"score": "0-1", "leg_result": "输"}, ...}
        pnl: 本单净盈亏 (如 -30 或 +132.47)
        """
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "combo_type": combo_type,
            "stake": stake,
            "pnl": pnl,
            "legs": []
        }
        exec_error = False

        for leg in legs:
            match = leg.get('match', '')
            bet = leg.get('bet', '')
            leg_rec = {
                "match": match,
                "bet": bet,
                "score": leg.get('score', ''),
                "leg_result": leg.get('leg_result', ''),
            }
            bb = best_bets_map.get(match)
            if bb:
                bb_name = bb.get('name', '')
                leg_rec['best_bet'] = bb_name
                leg_rec['best_bet_prob'] = bb.get('prob')
                # 比对: 实际选腿 != best_bet → 执行失误
                if not self._bet_equal(bet, bb_name):
                    leg_rec['execution_error'] = True
                    leg_rec['error_reason'] = f"选腿[{bet}] ≠ best_bet[{bb_name}](胜率{bb.get('prob', 0):.1%})"
                    exec_error = True
                else:
                    leg_rec['execution_error'] = False
            else:
                leg_rec['best_bet'] = None
                leg_rec['execution_error'] = None  # 无法校验

            record['legs'].append(leg_rec)

        record['execution_error'] = exec_error
        if exec_error:
            lost_legs = [l for l in record['legs'] if l.get('leg_result') == '输' and l.get('execution_error')]
            record['note'] = "⚠️ 存在执行失误: 实际选腿与best_bet(最高胜率腿)不一致"
            if lost_legs:
                record['note'] += "; 失误腿导致输单: " + "、".join(l['match'] for l in lost_legs)

        self.review_data['records'].append(record)
        self._save_review()
        return record

    def get_stats(self):
        return self.review_data.get('stats', {})


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    v = BetValidator()

    # 测试第2层: 用湖北案例
    print("=" * 70)
    print("第2层测试: 投注生成校验 (湖北青年星案例)")
    best_bets_map = {
        "湖北青年星 vs 江西庐山": {"name": "小2.25", "prob": 0.8525, "odds": 1.72, "ev": 0.466},
        "上海海港B vs 山西崇德荣海": {"name": "小2.25", "prob": 0.852, "odds": 1.73, "ev": 0.475},
    }
    # 错误案例: 湖北选让球腿
    bad_legs = [
        {"match": "上海海港B vs 山西崇德荣海", "bet": "小2.25"},
        {"match": "湖北青年星 vs 江西庐山", "bet": "主队+0/0.5"},
    ]
    ok, errors, warnings = v.verify_bet_legs(bad_legs, best_bets_map)
    print("选腿: 海港B小2.25 + 湖北主+0/0.5")
    print(f"校验结果: {'✅ 通过' if ok else '❌ 拦截'}")
    for e in errors:
        print("  ❌", e)
    for w in warnings:
        print("  ", w)

    print()
    # 正确案例
    good_legs = [
        {"match": "上海海港B vs 山西崇德荣海", "bet": "小2.25"},
        {"match": "湖北青年星 vs 江西庐山", "bet": "小2.25"},
    ]
    ok, errors, warnings = v.verify_bet_legs(good_legs, best_bets_map)
    print("选腿: 海港B小2.25 + 湖北小2.25(改小球)")
    print(f"校验结果: {'✅ 通过' if ok else '❌ 拦截'}")
    for e in errors:
        print("  ❌", e)
    for w in warnings:
        print("  ", w)
