import io,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
s=io.open("src/odds/api_router.py",encoding="utf-8").read()
i=s.find("def get_active_key")
print(s[i:i+3000])
