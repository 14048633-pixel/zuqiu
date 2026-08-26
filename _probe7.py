import io,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s=io.open("prediction_v2/scan_upcoming.py",encoding="utf-8").read()
i=s.find("def parse_snapshots")
j=s.find("def analyze_match", i)
seg=s[i:j]
print(seg[-3200:])
