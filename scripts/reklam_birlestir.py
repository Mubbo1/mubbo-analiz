#!/usr/bin/env python3
"""Reklam toplayıcısının yeni bulduğu reklamları (data/reklam_ham.bin) sitedeki reklam dosyalarına ekler.

Kullanım (depo kökünde): MUBBO_SIFRE='...' python3 scripts/reklam_birlestir.py
- Yalnız 10 Ekim 2026 ve sonrasında yayına girmiş, daha önce eklenmemiş reklamlar eklenir
  (öncesi ilk toplamada zaten var). Eklenen reklam kodları data/reklam_eklenen.json'da tutulur.
- Reklamın hedef/kart linkleri rakip kataloğundaki ürünlerle eşleştirilir (ürün adı, fiyat, link, görsel).
- Aylık sayılar (reklam_ozet) güncellenir; dosyalar 7 MB'lık paketlere yeniden bölünür.
"""
import collections, datetime as dt, glob, json, os, re, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_eslestir as tg

DATA = tg.DATA
BASLANGIC = '2026-10-10'
TUR = {'VIDEO': 'Video', 'IMAGE': 'Görsel', 'CAROUSEL': 'Kaydırmalı', 'DPA': 'Katalog', 'DCO': 'Dinamik', 'MULTI_IMAGES': 'Kaydırmalı'}
TZ = dt.timezone(dt.timedelta(hours=3))


def yol(l):
    try:
        p = urllib.parse.urlsplit(l.strip())
    except Exception:
        return ''
    host = p.netloc.lower().removeprefix('www.')
    return host + urllib.parse.unquote(p.path).rstrip('/').lower()


def main():
    ozel = tg.ozel_anahtar()
    # toplayıcı her çalışmada birkaç markayı tarar (Meta kısıtlaması) ve data/reklam_ham/<zaman>.bin yazar;
    # eski tek dosya (reklam_ham.bin) da okunur. Aynı reklam birden çok parçada olabilir.
    parcalar = sorted(glob.glob(os.path.join(DATA, 'reklam_ham', '*.bin')))
    hp = os.path.join(DATA, 'reklam_ham.bin')
    if os.path.exists(hp):
        parcalar.insert(0, hp)
    if not parcalar:
        print('ham reklam verisi yok; toplayıcı henüz veri yazmadı'); return
    ham = {'markalar': {}}; ham_gor = set()
    for f in parcalar:
        try:
            h = tg.coz(f, ozel)
        except Exception as e:
            print('okunamadı:', f, e); continue
        for marka, ads in (h.get('markalar') or {}).items():
            for a in ads:
                if str(a['id']) not in ham_gor:
                    ham_gor.add(str(a['id'])); ham['markalar'].setdefault(marka, []).append(a)
    ozet = tg.coz(os.path.join(DATA, 'reklam_ozet.bin'), ozel)
    rows = []
    for f in sorted(glob.glob(os.path.join(DATA, 'reklam_[0-9]*.bin'))):
        rows += tg.coz(f, ozel)
    ep = os.path.join(DATA, 'reklam_eklenen.json')
    eklenen = set(json.load(open(ep))) if os.path.exists(ep) else set()
    gorulen = {str(r['id']) for r in rows} | eklenen
    kat = tg.katalog(ozel); kyol = {}
    for r in kat:
        kyol.setdefault(yol(r['l']), r)
    simdi = dt.datetime.now(TZ)
    yeni_say = collections.Counter(); yeni_ozet = collections.Counter(); yeni_vid = collections.Counter()
    by = collections.defaultdict(list)
    for r in rows:
        by[r['m']].append(r)
    for marka, ads in (ham.get('markalar') or {}).items():
        for a in ads:
            if str(a['id']) in gorulen or not a.get('baslangic'):
                continue
            st = dt.datetime.fromtimestamp(int(a['baslangic']), TZ)
            if st.strftime('%Y-%m-%d') < BASLANGIC:
                continue
            linkler = [a.get('hedef') or ''] + [c.get('link') or '' for c in a.get('kartlar') or []]
            ur = []
            for l in linkler:
                k = kyol.get(yol(l)) if l else None
                if k and all(u['link'] != k['l'] for u in ur):
                    g = k.get('g')
                    ur.append({'ad': k['u'], 'fiyat': k['f'], 'eski': k.get('e'), 'link': k['l'],
                               'gorsel': g if (g or '').startswith('data:') else (('data:image/webp;base64,' + g) if g else None)})
            hedef = a.get('hedef') or next((c.get('link') for c in a.get('kartlar') or [] if c.get('link')), '') or ''
            if 'fb.com/canvas_doc' in hedef:
                hedef = ''
            satir = {'id': str(a['id']), 'tarih': st.strftime('%Y-%m-%d'), 'gun': max(0, (simdi - st).days), 'tur': TUR.get(a.get('format'), 'Diğer'),
                     'video': bool(a.get('video')), 'metin': (a.get('metin') or a.get('baslik') or '').strip()[:300], 'hedef': hedef,
                     'kapak': a.get('kapak'), 'urunler': ur[:6], 'eslesme': 'link' if ur else '', 'adet': int(a.get('adet') or 1), 'ilk': st.strftime('%Y-%m-%d'), 'm': marka}
            # aynı görsel+ürün+ay+tür olan kart varsa sayısını artır
            key = (tuple(u['link'] for u in satir['urunler']), satir['tarih'][:7], satir['tur'], satir['metin'][:60])
            es = next((r for r in by[marka] if (tuple(u['link'] for u in (r.get('urunler') or [])), str(r['tarih'])[:7], r['tur'], (r.get('metin') or '')[:60]) == key), None)
            if es:
                es['adet'] = int(es.get('adet') or 1) + satir['adet']; es['ilk'] = min(es.get('ilk') or es['tarih'], satir['tarih'])
            else:
                by[marka].append(satir)
            eklenen.add(satir['id']); yeni_say[marka] += 1
            yeni_ozet[(marka, satir['tarih'][:7])] += satir['adet']
            if satir['video']:
                yeni_vid[(marka, satir['tarih'][:7])] += satir['adet']
    if not yeni_say:
        print('Eklenecek yeni reklam yok.'); return
    # özet
    idx = {(o['marka'], o['ay']): o for o in ozet}
    for (m, ay), n in yeni_ozet.items():
        o = idx.get((m, ay))
        if o:
            o['reklam'] += n; o['video'] += yeni_vid[(m, ay)]
        else:
            o = {'marka': m, 'dataset': '', 'ay': ay, 'reklam': n, 'video': yeni_vid[(m, ay)]}; ozet.append(o); idx[(m, ay)] = o
    # paketle (7 MB)
    boy = {m: len(json.dumps(v, ensure_ascii=False)) for m, v in by.items()}
    kutular = []
    for m in sorted(boy, key=lambda m: -boy[m]):
        for b in kutular:
            if b['sz'] + boy[m] < 7.0e6:
                b['sz'] += boy[m]; b['m'].append(m); break
        else:
            kutular.append({'sz': boy[m], 'm': [m]})
    for f in glob.glob(os.path.join(DATA, 'reklam_[0-9]*.bin')):
        os.remove(f)
    hedefds = {}
    for i, b in enumerate(kutular):
        paket = [r for m in b['m'] for r in sorted(by[m], key=lambda r: str(r['tarih']), reverse=True)]
        open(os.path.join(DATA, f'reklam_{i + 1}.bin'), 'wb').write(tg.sifrele(paket, ozel))
        for m in b['m']:
            hedefds[m] = f'reklam_{i + 1}'
    for o in ozet:
        o['dataset'] = hedefds.get(o['marka'], o['dataset'])
    ozet.sort(key=lambda o: (o['marka'], o['ay']))
    open(os.path.join(DATA, 'reklam_ozet.bin'), 'wb').write(tg.sifrele(ozet, ozel))
    json.dump(sorted(eklenen), open(ep, 'w'))
    open(os.path.join(DATA, 'reklam_durum.json'), 'w').write(json.dumps({'son': simdi.isoformat(timespec='seconds'), 'eklenen': sum(yeni_say.values()), 'markalar': dict(yeni_say)}, ensure_ascii=False))
    print('Eklendi:', dict(yeni_say), '| paket sayısı', len(kutular))


if __name__ == '__main__':
    main()
