import io,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s=io.open("prediction_v2/scan_upcoming.py",encoding="utf-8").read()
i=s.find("def parse_snapshots")
seg=s[i:i+9000]
# 找 ev["league"] 或 "league" 组装处
import re
for mm in re.finditer(r'ev\[|events\[key\]|m\["league"\]|"league":', seg):
    pass
# 直接打印 _group_by_line 之后部分
j=seg.find("def _group_by_line")
k=seg.find("def _finalize", j)
# 打印 parse_snapshots 的后 4000 字符
print(seg[-4000:])
