import io,os,sys
sys.path.insert(0, r"D:\足球分析\form_phase0")
from fetch_live_48h import simpl
tests = [
    ("Brøndby IF","Brondby IF"),
    ("Sønderjyske Fodbold","SonderjyskE"),
    ("Gimnasia y Esgrima Mendoza","Gimnasia Mendoza"),
    ("CA Talleres","Talleres"),
]
for a,b in tests:
    sa,sb = simpl(a), simpl(b)
    print(repr(sa), repr(sb), "OK" if sa==sb else "MISMATCH")
