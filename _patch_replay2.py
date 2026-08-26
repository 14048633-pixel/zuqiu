import io
p = r"_replay_adj.py"
src = io.open(p, encoding="utf-8").read()
src = src.replace(
    """    def _pt(s):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None""",
    """    def _pt(s):
        try:
            d = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d
        except Exception:
            return None""")
io.open(p, "w", encoding="utf-8").write(src)
print("patched2 ok")
