import io,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s=io.open("form_phase0/analyze_48h_v2.py",encoding="utf-8").read()
i=s.find("hist = ")
if i<0: i=s.find("hist={")
if i<0: i=s.find("# ---- 历史")
print(s[i:i+2200])
