import io,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s=io.open("form_phase0/analyze_48h_v2.py",encoding="utf-8").read()
i=s.find("def main")
j=s.find("hist = ", i)
print(s[i:j+400])
