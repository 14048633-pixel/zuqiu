import io,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s=io.open("prediction_v2/scan_upcoming.py",encoding="utf-8").read()
i=s.find("def parse_snapshots")
seg=s[i:i+9500]
k=seg.find('rec = {')
print(seg[max(0,k-1500):k+1800])
