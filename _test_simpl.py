import io,os,sys,re,unicodedata
sys.path.insert(0, os.path.join(r"D:\足球分析","prediction_v2"))
from src.live_odds import normalize_team
_GENERIC = {"if","fc","ik","sk","cf","sc","ac","as","us","rb","ss","c","ff","ifk","ca","cd","bk","sd","ud","oe","ssd","apf","ba","afc","aik","fk","vfl","sv","bv","tsg","sg","cd"}
def simpl(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = normalize_team(s)
    words = [w for w in s.split() if w not in _GENERIC]
    return re.sub(r"[^a-z0-9]+", "", " ".join(words))
tests = [
    ("Brøndby IF","Brondby IF"),
    ("Sønderjyske Fodbold","SonderjyskE"),
    ("Gimnasia y Esgrima Mendoza","Gimnasia Mendoza"),
    ("CA Talleres","Talleres"),
]
for a,b in tests:
    print(repr(simpl(a)), repr(simpl(b)), "OK" if simpl(a)==simpl(b) else "MISMATCH")
