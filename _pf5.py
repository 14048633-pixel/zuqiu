import io
p=r"form_phase0\_refetch5.py"
s=io.open(p,encoding="utf-8").read()
old='''sys.path.insert(0, os.path.join(ROOT, "src", "odds"))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from api_router import OddsApiRouter
from live_odds import fetch_league_odds, flatten_events, append_snapshots, snapshots_path
import scan_upcoming as SU'''
new='''sys.path.insert(0, os.path.join(ROOT, "src", "odds"))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2", "src"))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from api_router import OddsApiRouter
from live_odds import fetch_league_odds, flatten_events, append_snapshots, snapshots_path
import scan_upcoming as SU'''
assert old in s
s=s.replace(old,new,1)
io.open(p,"w",encoding="utf-8").write(s)
print("patched")
