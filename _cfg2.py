import io,sys,os,glob
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# 找 cup_coeffs 加载文件
s=io.open("prediction_v2/scan_upcoming.py",encoding="utf-8").read()
i=s.find("def _load_cup_coeffs")
print(s[i:i+900])
