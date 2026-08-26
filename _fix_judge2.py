import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
src = io.open(r"D:\足球分析\_gen_final_report.py", encoding='utf-8').read()
old = """        if diff == 0:
            if abs(line) == 0.25:
                # 平局 + 四分之一盘: 受让方半赢
                return ('半赢' if line > 0 else '半输'), f"让球后平 {adj_h:.2f}-{adj_a:.2f}"
            return '走水', f"让球后 {adj_h:.2f}-{adj_a:.2f}"
        return ('赢' if diff > 0 else '输'), f"让球后 {adj_h:.2f}-{adj_a:.2f}\""""
new = """        if diff == 0:
            if abs(line) == 0.25:
                # 平局 + 四分之一盘: 受让方半赢
                return ('半赢' if line > 0 else '半输'), f"让球后平 {adj_h:.2f}-{adj_a:.2f}"
            return '走水', f"让球后 {adj_h:.2f}-{adj_a:.2f}"
        win = (diff > 0) if side == '主' else (diff < 0)   # diff>0 主赢盘; 方向让X看X是否赢盘
        return ('赢' if win else '输'), f"让球后 {adj_h:.2f}-{adj_a:.2f}\""""
assert old in src, "old judge block not found"
src = src.replace(old, new)
# 同时把 0.2 归一为 0.25 四分之一盘
old2 = "        line = line if abs(line) != 0.2 else (0.25 if line > 0 else -0.25)"
new2 = "        line = (0.25 if line > 0 else -0.25) if abs(line) == 0.2 else line"
if old2 in src:
    src = src.replace(old2, new2)
io.open(r"D:\足球分析\_gen_final_report.py", 'w', encoding='utf-8').write(src)
print("judge fixed v2")
