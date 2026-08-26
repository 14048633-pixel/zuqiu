import io
p=r'form_phase0\_patch_live2match.py'
s=io.open(p,encoding='utf-8').read()
s=s.replace('import pandas as pd\n', 'import pandas as pd\nimport sys\nsys.stdout.reconfigure(encoding="utf-8", errors="replace")\n')
io.open(p,'w',encoding='utf-8').write(s)
print("ok")
