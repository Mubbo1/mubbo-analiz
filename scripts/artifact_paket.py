#!/usr/bin/env python3
"""Claude'daki fotoğrafla fiyat karşılaştırma sayfası için katalog dosyaları üretir.
Her marka: katalog_<anahtar>.json = [{u, f, e, l, g: küçük görsel (data URL), v: görüntü vektörü (base64 int8)}]
Kaynak: depodaki günlük katalog (yalnız stoktakiler), küçük görseller (data/kimg*), vektörler (data/emb).
Kullanım: MUBBO_SIFRE=... python3 scripts/artifact_paket.py <çıktı klasörü>
"""
import base64, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_eslestir as t, gomme as g
ROOT = g.ROOT; DATA = os.path.join(ROOT, 'data')
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, '.yayin', 'foto')
os.makedirs(out, exist_ok=True)
o = t.ozel_anahtar()
img = {}
for f in glob.glob(os.path.join(DATA, 'kimg', '*.bin')) + glob.glob(os.path.join(DATA, 'kimg_ek', '*.bin')):
    try: img.update(t.coz(f, o))
    except Exception as e: print('görsel okunamadı', f, e)
ozet = []
for f in sorted(glob.glob(os.path.join(DATA, 'katalog', '*.bin'))):
    key = os.path.basename(f)[:-4]
    try: rows = t.coz(f, o)
    except Exception as e: print('katalog okunamadı', key, e); continue
    dim, vek = g.oku(key)
    satir = []; nv = ng = 0
    for r in rows:
        if not r.get('l') or not r.get('u'): continue
        x = {'u': r['u'], 'f': r.get('f'), 'e': r.get('e'), 'l': r['l']}
        gg = img.get(r['l'])
        if gg: x['g'] = gg; ng += 1
        v = vek.get(g.hsh(r['l']))
        if v: x['v'] = base64.b64encode(v).decode(); nv += 1
        satir.append(x)
    if not satir: continue
    json.dump(satir, open(os.path.join(out, 'katalog_' + key + '.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    ozet.append([rows[0].get('m') or key, key, len(satir), ng, nv])
    print(key, len(satir), 'görsel', ng, 'vektör', nv, flush=True)
json.dump(ozet, open(os.path.join(out, 'ozet.json'), 'w'), ensure_ascii=False)
