import io,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s=io.open("form_phase0/build_plan_48h.py",encoding="utf-8").read()
i=s.find("# ---- 模型信号 ----")
print(s[i:i+1400])
