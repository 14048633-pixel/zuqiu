import io
p=r'form_phase0\_patch_live2match.py'
s=io.open(p,encoding='utf-8').read()
s=s.replace('print("MATCHED:", lg, m["home"], "vs", m["away"], rec.get("dir_1x2"), "|", rec.get("dir_ou"))',
            'print("MATCHED:", lg, m["home"], "vs", m["away"], str(rec.get("dir_1x2")).encode("ascii","replace").decode(), "|", str(rec.get("dir_ou")).encode("ascii","replace").decode())')
io.open(p,'w',encoding='utf-8').write(s)
print("ok")
