# 修复合并脚本: Hallescher 判断 + 重新生成 results_all
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
src = io.open(r"D:\足球分析\_merge_results.py", encoding='utf-8').read()
old = "if _norm(h).startswith('hallescher') and _norm(a).startswith('schalke'):"
new = "if 'hallescher' in _norm(h) and 'schalke' in _norm(a):"
assert old in src
src = src.replace(old, new)
io.open(r"D:\足球分析\_merge_results.py", 'w', encoding='utf-8').write(src)
print("merge script fixed")
