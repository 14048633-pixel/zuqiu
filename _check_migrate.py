import sys, os, json, shutil
sys.stdout.reconfigure(encoding='utf-8')

# 检查冷门引擎相关文件
files = [
    'src/features/upset_engine_v2.py',
    'src/features/upset_engine.py',
    'src/features/feature_extractor.py',
    'src/features/football_agent.py',
    'auto_sop.py',
    '.env',
    'requirements.txt',
]
print('冷门引擎相关文件:')
for f in files:
    ok = os.path.exists(f)
    size = os.path.getsize(f) if ok else 0
    print(f'  {"OK " if ok else "MISS"} {f} ({size} bytes)')

# 检查验证数据
print('\n冷门引擎验证数据:')
vdata = [
    'strategy_data/bets_20260805_cl2.json',
    'strategy_data/cl2_recollated_20260805.json',
]
for f in vdata:
    ok = os.path.exists(f)
    print(f'  {"OK " if ok else "MISS"} {f}')

# 冷门引擎运行依赖
print('\n冷门引擎依赖:')
try:
    import requests
    print('  OK requests')
except:
    print('  MISS requests')
try:
    import numpy
    print('  OK numpy')
except:
    print('  MISS numpy')
