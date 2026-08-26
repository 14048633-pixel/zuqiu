import io
p = r"_gen_best9.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))\nsys.path.insert(0, ROOT)',
              'sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))\nsys.path.insert(0, os.path.join(ROOT, "prediction_v2", "src"))\nsys.path.insert(0, os.path.join(ROOT, "src", "models"))\nsys.path.insert(0, ROOT)')
io.open(p, "w", encoding="utf-8").write(s)
print("ok")
