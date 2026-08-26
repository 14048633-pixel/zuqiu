import sys, os, json, glob
sys.stdout.reconfigure(encoding='utf-8')
os.chdir('D:/ai/电脑庄家/足球竞猜模型训练')
sys.path.insert(0, '.')
sys.path.insert(0, 'src/strategy')
sys.path.insert(0, 'src/rules')
sys.path.insert(0, 'src/features')
from auto_sop import FootballPredictor

# 从历史记录重建数据, 用修复后代码重跑
for kw in ['忠南','华城','水原','庆南','龙仁']:
    files = sorted(glob.glob('analysis_records/*' + kw + '*'))
    if not files: continue
    j = json.load(open(files[-1], encoding='utf-8'))
    # 重建 raw_text
    raw = j.get('match') + '\n韩国K2联赛\n'
    raw += '独赢 - %s %s\n' % (j.get('odds_home',''), j.get('odds_away',''))
    raw += '让球 %s %s\n' % (j.get('hdp_home',''), j.get('hdp_away',''))
    raw += '大小球 2.5 大1.83 小2.03\n'
    raw += '近10场战绩\n' + j['steps'].get('step2_1',{}).get('result','') + '\n'
    raw += '历史交锋\n' + j['steps'].get('step2_2',{}).get('result','') + '\n'
    raw += '伤病停赛\n' + j['steps'].get('step2_3',{}).get('result','') + '\n'
    raw += '战意\n' + (j.get('user_motivation','') or '')
    try:
        sop = FootballPredictor()
        data = {'status':'pre_match','league':'韩国K2联赛','raw_text':raw}
        rec = sop.analyze(data)
        feats = rec['steps'].get('step2_1',{}).get('features',{})
        poi = rec['steps'].get('step8',{}).get('poisson',{})
        s31 = rec['steps'].get('step31_ev_calc',{})
        bb = s31.get('best_bet',{})
        print('%s: away_gf=%s λ=%s/%s best=%s(%.0f%%)' % (
            rec.get('match'), feats.get('away_gf'),
            poi.get('lambda_home'), poi.get('lambda_away'),
            bb.get('name'), bb.get('prob',0)*100))
    except Exception as ex:
        print('%s: ERROR %s' % (kw, str(ex)[:60]))
