#!/usr/bin/env python3
"""Sitenin hızlı açılması için verileri tek dosyada toplar (GitHub Actions'ta, MUBBO_SIFRE ile çalışır).

1) data/katalog_site.bin: bütün rakip katalogları tek dosyada; sitesi 1 günden uzun süredir okunamayan rakipler
   ve aksesuarlar (çorap, iç çamaşırı, çanta, kemer, takı...) çıkarılmış. Site 49 dosya yerine bunu indirir.
2) data/yeni/arsiv.bin: saatlik "yeni ürün" parçaları birleştirilir (yüzlerce küçük dosya yerine bir dosya).
"""
import datetime as dt, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_eslestir as t
from artifact_tel import aksesuar, tur as urun_turu


def giyim_degil(r):
    """Sitede yalnız kıyafet, pantolon ve ayakkabı: aksesuar, çorap, iç çamaşırı, takı ve türü belli olmayan ucuz ürünler çıkar"""
    f = r.get('f') or 0
    return aksesuar(r.get('u') or '') or f < 30 or (f < 150 and urun_turu(r.get('u') or '') == 'diger')

DATA = t.DATA


def katalog(o):
    durum = json.load(open(os.path.join(DATA, 'katalog_durum.json')))
    sinir = (dt.datetime.utcnow() - dt.timedelta(days=1)).strftime('%Y-%m-%d')
    rows, eski = [], []
    for k, m in (durum.get('markalar') or {}).items():
        if not (m.get('durum') == 'ok' or (m.get('tarih') or '') >= sinir):
            eski.append(m.get('marka')); continue
        f = os.path.join(DATA, 'katalog', k + '.bin')
        if not os.path.exists(f):
            continue
        for r in t.coz(f, o):
            if r.get('u') and not giyim_degil(r):
                rows.append(r)
    open(os.path.join(DATA, 'katalog_site.bin'), 'wb').write(t.sifrele({'son': durum.get('son'), 'eski': eski, 'rows': rows}, o))
    print('katalog_site:', len(rows), 'ürün;', 'okunamayan:', eski)


def yeni_birlestir(o, kalan=6):
    pp = os.path.join(DATA, 'yeni_parcalar.json')
    if not os.path.exists(pp):
        return
    parcalar = json.load(open(pp))
    eski = [p for p in parcalar if p != 'arsiv.json'][:-kalan] if len(parcalar) > kalan + 1 else []
    if not eski:
        return
    ap = os.path.join(DATA, 'yeni', 'arsiv.bin')
    arsiv = t.coz(ap, o) if os.path.exists(ap) else []
    for p in eski:
        f = os.path.join(DATA, 'yeni', p[:-5] + '.bin')
        if os.path.exists(f):
            arsiv += t.coz(f, o); os.remove(f)
    open(ap, 'wb').write(t.sifrele(arsiv, o))
    yeni = ['arsiv.json'] + [p for p in parcalar if p != 'arsiv.json' and p not in eski]
    json.dump(yeni, open(pp, 'w'))
    print('yeni arşiv:', len(arsiv), 'ürün;', len(eski), 'parça birleştirildi; kalan', len(yeni))


def satis(o, gun=30):
    gp = os.path.join(DATA, 'satis_gun.json')
    if not os.path.exists(gp):
        return
    adlar = json.load(open(gp))[-gun:]; gunler = []
    for a in adlar:
        f = os.path.join(DATA, 'satis_gun', a[:-5] + '.bin' if a.endswith('.json') else a)
        try: gunler.append(t.coz(f, o))
        except Exception: gunler.append(None)
    open(os.path.join(DATA, 'satis_toplu.bin'), 'wb').write(t.sifrele({'adlar': adlar, 'gunler': gunler}, o))
    print('satis_toplu:', len(adlar), 'gün')


def sosyal(o):
    gp = os.path.join(DATA, 'sosyal_gunler.json')
    if not os.path.exists(gp):
        return
    gunler = json.load(open(gp)); dosyalar = []
    for g in gunler:
        f = os.path.join(DATA, 'sosyal', g[:-5] + '.bin' if g.endswith('.json') else g)
        try: dosyalar.append(t.coz(f, o))
        except Exception: dosyalar.append(None)
    open(os.path.join(DATA, 'sosyal_toplu.bin'), 'wb').write(t.sifrele({'gunler': gunler, 'dosyalar': dosyalar}, o))
    print('sosyal_toplu:', len(gunler), 'gün')


if __name__ == '__main__':
    o = t.ozel_anahtar()
    if 'katalog' in sys.argv[1:] or len(sys.argv) == 1:
        katalog(o); satis(o)
    if 'yeni' in sys.argv[1:] or len(sys.argv) == 1:
        yeni_birlestir(o)
    if 'sosyal' in sys.argv[1:] or len(sys.argv) == 1:
        sosyal(o)
