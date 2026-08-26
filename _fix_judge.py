# 重写报告脚本的让球判定，重新生成 final_report
import io, sys, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
src = io.open(r"D:\足球分析\_gen_final_report.py", encoding='utf-8').read()

old_judge = """def judge_leg(name, hs, as_, draw_prob=None):
    \"\"\"返回 (结果, 说明) 结果: 赢/输/走水/半赢/半输\"\"\"
    ov = parse_total_line(name)
    if ov:
        side, line = ov
        total = hs + as_
        if side == '大':
            return ('赢' if total > line else '走水' if total == line else '输'), f"总{total}"
        else:
            return ('赢' if total < line else '走水' if total == line else '输'), f"总{total}"
    ah = parse_ah(name)
    if ah:
        side, line = ah
        gh = -line if side == '主' else line   # 主队让球值(带符号), 客队相反
        ga = -gh
        adj_h, adj_a = hs + gh, as_ + ga
        diff = adj_h - adj_a
        if diff == 0:
            if abs(line) == 0.25 or (abs(line)*10) % 5 == 2.5:
                return ('半赢' if (side=='主' and gh>0) or (side=='客' and line>0) else '半输'), f"让球后平 {adj_h}-{adj_a}"
            return '走水', f"让球后 {adj_h}-{adj_a}"
        win = diff > 0
        if abs(line) == 0.25:
            # 四分之一盘不存在完全走水; diff==0 时部分赢
            return ('赢' if win else '输'), f"让球后 {adj_h}-{adj_a}"
        return ('赢' if win else '输'), f"让球后 {adj_h}-{adj_a}"
    if name.startswith('1X2'):
        side = name.replace('1X2','').strip()
        if side == '主胜': want='home'
        elif side == '客胜': want='away'
        else: want='draw'
        if want=='home': return ('赢' if hs>as_ else '输'), f"{hs}-{as_}"
        if want=='away': return ('赢' if as_>hs else '输'), f"{hs}-{as_}"
        return ('赢' if hs==as_ else '输'), f"{hs}-{as_}"
    return '?', ''"""

new_judge = """def judge_leg(name, hs, as_, draw_prob=None):
    \"\"\"返回 (结果, 说明) 结果: 赢/输/走水/半赢/半输\"\"\"
    ov = parse_total_line(name)
    if ov:
        side, line = ov
        total = hs + as_
        if side == '大':
            return ('赢' if total > line else '走水' if total == line else '输'), f"总{total}"
        else:
            return ('赢' if total < line else '走水' if total == line else '输'), f"总{total}"
    ah = parse_ah(name)
    if ah:
        side, line = ah
        gh = line if side == '主' else -line   # 主队带符号让球值: 让球主(+X)=主受让X, 让球客(+X)=客受让X(主让X)
        ga = -gh
        adj_h, adj_a = hs + gh, as_ + ga
        diff = adj_h - adj_a
        if diff == 0:
            if abs(line) == 0.25:
                # 平局 + 四分之一盘: 受让方半赢
                return ('半赢' if line > 0 else '半输'), f"让球后平 {adj_h:.2f}-{adj_a:.2f}"
            return '走水', f"让球后 {adj_h:.2f}-{adj_a:.2f}"
        return ('赢' if diff > 0 else '输'), f"让球后 {adj_h:.2f}-{adj_a:.2f}"
    if name.startswith('1X2'):
        side = name.replace('1X2','').strip()
        if side == '主胜': want='home'
        elif side == '客胜': want='away'
        else: want='draw'
        if want=='home': return ('赢' if hs>as_ else '输'), f"{hs}-{as_}"
        if want=='away': return ('赢' if as_>hs else '输'), f"{hs}-{as_}"
        return ('赢' if hs==as_ else '输'), f"{hs}-{as_}"
    return '?', ''"""

assert old_judge in src
src = src.replace(old_judge, new_judge)
io.open(r"D:\足球分析\_gen_final_report.py", 'w', encoding='utf-8').write(src)
print("judge fixed")
