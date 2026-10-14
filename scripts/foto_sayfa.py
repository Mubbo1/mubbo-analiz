#!/usr/bin/env python3
"""Fotoğrafla arama sayfasını (Claude Artifact) depodaki güncel kataloglardan üretir.

Kullanım (depo kökünde): MUBBO_SIFRE='...' python3 scripts/foto_sayfa.py /tmp/foto
Çıktı: /tmp/foto/index.html (telefon için gömülü katalog + küçük görseller) ve
/tmp/foto/katalog_<anahtar>.json (bilgisayarda kullanılan, daha büyük görselli dosyalar).
Sonra Claude, Artifact aracıyla url=https://claude.ai/artifact/FsMseVP29e4mnyrHpH4Yt1,
file_path=/tmp/foto/index.html, files={katalog_<anahtar>.json: /tmp/foto/katalog_<anahtar>.json, ...} yayınlar.
"""
import base64, glob, gzip, io, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_eslestir as tg
from PIL import Image

ROOT = tg.ROOT; DATA = tg.DATA
BUTCE = 13_000_000   # gömülü verinin üst sınırı (sayfa 16 MB'ı geçmesin)


def main(out):
    os.makedirs(out, exist_ok=True)
    ozel = tg.ozel_anahtar()
    durum = json.load(open(os.path.join(DATA, 'katalog_durum.json')))['markalar']
    g = {}
    for f in glob.glob(os.path.join(DATA, 'kimg', '*.bin')) + sorted(glob.glob(os.path.join(DATA, 'kimg_ek', '*.bin'))):
        g.update(tg.coz(f, ozel))
    markalar = []
    for key, d in sorted(durum.items(), key=lambda x: -(x[1].get('urun') or 0)):
        p = os.path.join(DATA, 'katalog', key + '.bin')
        if not os.path.exists(p):
            continue
        rows = [r for r in tg.coz(p, ozel) if r.get('l')]
        for r in rows:
            r['g'] = g.get(r['l'])
        json.dump([{k: r.get(k) for k in ('u', 'f', 'e', 'l', 'g')} for r in rows], open(os.path.join(out, f'katalog_{key}.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
        markalar.append((d.get('marka') or rows[0]['m'], key, rows))
    toplam = sum(len(r) for _, _, r in markalar)
    text = {key: [[r['u'], r['f'], r['e'], r['l']] for r in rows] for _, key, rows in markalar}
    gz = base64.b64encode(gzip.compress(json.dumps(text, ensure_ascii=False, separators=(',', ':')).encode(), 9)).decode()
    # sayfaya yalnız yazı verisi gömülür (telefon görünümü için); görseller katalog dosyalarından gelir
    blok = '<script id="kat-text" type="text/plain">' + gz + '</script>'
    W = H = 0
    brands = ','.join(json.dumps([m, key, len(rows)], ensure_ascii=False) for m, key, rows in markalar)
    s = open(os.path.join(ROOT, 'scripts', 'foto_sablon.html')).read()
    s = s.replace('<!--INLINE_DATA-->', blok).replace('/*BRANDS*/', brands)
    open(os.path.join(out, 'index.html'), 'w').write(s)
    print(f'{len(markalar)} marka, {toplam} ürün, sayfa {len(s) / 1e6:.1f} MB -> {out}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/tmp/foto')
