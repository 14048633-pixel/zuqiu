import io,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s=io.open("form_phase0/analyze_48h_v2.py",encoding="utf-8").read()
i=s.find("def form_score")
if i<0: i=s.find("def _form")
print(s[i:i+2600] if i>=0 else "not found")
# 找 main 里 form 推理调用
j=s.find("form_score(")
if j<0: j=s.find("_form(")
print("===== call site =====")
print(s[max(0,j-1200):j+900] if j>=0 else "")
