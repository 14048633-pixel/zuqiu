"""
凯利公式资金管理
根据 edge 和赔率计算最优下注比例
"""
def kelly_fraction(prob, odds, fraction=0.25):
    """
    凯利公式: f* = (p * odds - 1) / (odds - 1)
    - prob: 你的模型概率 (0~1)
    - odds: 庄家赔率 (十进制)
    - fraction: 凯利系数 (保守用 0.25，激进用 0.5)
    返回: 建议下注比例 (占资金的百分比)
    """
    if odds <= 1 or prob <= 0:
        return 0
    f = (prob * odds - 1) / (odds - 1)
    if f <= 0:
        return 0
    return min(f * fraction, 0.2)  # 单注不超过 20%


def kelly_value_bet(prob, odds, bankroll, min_edge=0.03, kelly_frac=0.25):
    """
    返回: (建议投注额, edge, 凯利比例) 或 (0, edge, 0)
    """
    if odds <= 1 or prob <= 0:
        return 0, 0, 0
    edge = prob * odds - 1
    if edge < min_edge:
        return 0, edge, 0
    f = kelly_fraction(prob, odds, kelly_frac)
    stake = round(bankroll * f, 2)
    return stake, round(edge, 4), round(f, 4)


def simulate_kelly(bets_df, bankroll=1000, kelly_frac=0.25):
    """
    模拟凯利下注过程
    bets_df 需要列: prob, odds, result (1=赢, 0=输)
    返回: (最终资金, 每期资金列表, 总ROI)
    """
    bank = bankroll
    history = [bank]
    for _, r in bets_df.iterrows():
        stake, _, _ = kelly_value_bet(r["prob"], r["odds"], bank, min_edge=0, kelly_frac=kelly_frac)
        if stake > 0 and r.get("result") is not None:
            if r["result"] == 1:
                bank += stake * (r["odds"] - 1)
            else:
                bank -= stake
        history.append(bank)
    roi = (bank - bankroll) / bankroll * 100
    return bank, history, roi
