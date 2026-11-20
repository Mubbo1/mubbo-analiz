#!/usr/bin/env python3
"""Telegram ürünlerinin rakip karşılıklarını takip edilen rakiplere göre baştan hesaplar (rakip listesi değişince bir kez çalıştırılır).
Claude'un verdiği "aynı" kararları korunur (rakip takipteyse); benzerler görüntü vektörüyle yeniden bulunur."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_eslestir as tg, tg_otomatik as ot, gomme
from takip import TAKIP


def main():
    o = tg.ozel_anahtar(); rows, mat = ot.havuz(o); model = gomme.Model()
    U = {u['id']: u for u in tg.urunler(o)}; S = tg.sonuclar(o)
    for i, r in enumerate(S):
        r['ayni'] = [a for a in (r.get('ayni') or []) if a.get('marka') in TAKIP]
        gor = {a['link'] for a in r['ayni']}
        u = U.get(r['id'])
        if not u:
            r['benzer'] = [b for b in (r.get('benzer') or []) if b.get('marka') in TAKIP]; continue
        r['tur'], ad = ot.sec_benzer(model, rows, mat, u['fotolar'], u['metin'] + ' ' + (r.get('ozet') or ''))
        sec = [(s, x) for s, x in ad if x['l'] not in gor][:6]
        r['benzer'] = [{'no': j + 1, 'marka': x['m'], 'urun': x['u'], 'fiyat': x['f'], 'eski_fiyat': x.get('e'), 'link': x['l'], 'benzerlik': round(s, 3),
                        'karar': 'benzer', 'gorsel': tg.gorsel(x.get('g')) or x.get('gurl')} for j, (s, x) in enumerate(sec)]
        if i % 50 == 0: print(i, len(S), flush=True)
    open(os.path.join(tg.DATA, 'tg_sonuc.bin'), 'wb').write(tg.sifrele(S, o))
    hafif = [{k: r[k] for k in ('tarih', 'toptanci', 'kanal', 'ozet', 'post', 'foto', 'ayni') if k in r} for r in S if r.get('ayni')]
    open(os.path.join(tg.DATA, 'tg_toptan.bin'), 'wb').write(tg.sifrele(hafif, o))
    tg.liste_yaz(S, o)
    print(len(S), 'ürün;', sum(1 for r in S if r['ayni']), 'aynı;', sum(1 for r in S if r['benzer']), 'benzeri olan')


if __name__ == '__main__':
    main()
