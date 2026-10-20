#!/usr/bin/env python3
"""Eski Claude panosu (Dashboard artifact) için güncel veri dosyalarını üretir.

Kullanım: MUBBO_SIFRE='...' python3 scripts/pano_aktar.py <klasor>
Yazar: reklam_1..N.json, reklam_ozet.json, yeni_urunler.json (panonun beklediği biçimde, düz JSON dizi).
Claude bunları panoya dosya olarak yükleyip datasets/<ad> belgelerinin source.url alanını günceller.
"""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_eslestir as tg

def main(out):
    os.makedirs(out, exist_ok=True)
    o = tg.ozel_anahtar(); D = tg.DATA
    adlar = []
    for f in sorted(glob.glob(os.path.join(D, 'reklam_[0-9]*.bin'))) + [os.path.join(D, 'reklam_ozet.bin')]:
        ad = os.path.basename(f)[:-4]
        json.dump(tg.coz(f, o), open(os.path.join(out, ad + '.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
        adlar.append(ad)
    rows = tg.coz(os.path.join(D, 'yeni_urunler.bin'), o)
    gor = {r['link'] for r in rows}
    for f in sorted(glob.glob(os.path.join(D, 'yeni', '*.bin'))):
        for r in tg.coz(f, o):
            if r['link'] not in gor:
                gor.add(r['link']); rows.append(r)
    json.dump(rows, open(os.path.join(out, 'yeni_urunler.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    adlar.append('yeni_urunler')
    for a in adlar:
        p = os.path.join(out, a + '.json'); print(a, os.path.getsize(p))

if __name__ == '__main__':
    main(sys.argv[1])
