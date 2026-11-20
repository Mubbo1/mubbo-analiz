#!/usr/bin/env python3
"""Rakip ürünlerinin günlük geçmişi: fiyat değişiklikleri, tükenen ürünler ve hızla tükenmek üzere olanlar.

Her katalog yenilemesinden sonra (GitHub Actions, MUBBO_SIFRE ile) çalışır:
  data/gecmis/fiyat.bin  {link: [marka, ad, görsel, [[gün, fiyat, eski_fiyat], ...], ilk_gün, son_gün]}  (ürün detayı için)
  data/gecmis/stok.bin   {link_özeti: [[gün, adet], ...]}  (son 21 gün; stok adedini gösteren siteler)
  data/gecmis/olay.bin   [[gün, tür, link], ...]  (son 45 gün: 'dus' fiyat düştü, 'art' fiyat arttı, 'yeni', 'bitti' stoktan çıktı)
  data/degisim.bin       siteye özet: son 7 günün olayları + tükenmek üzere olanlar + günlük sayılar
İlk kurulum: python3 scripts/gecmis.py --git  (depo geçmişindeki günlük katalogları sırayla işler)
"""
import datetime as dt, glob, hashlib, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_eslestir as t
import yeni_urun as yu
from artifact_tel import aksesuar, tur as urun_turu

DATA = t.DATA
GD = os.path.join(DATA, 'gecmis')
SUPHE = {'Ferell Moda', 'Torias Man'}   # stok sayıları gerçek görünmüyor


def lh(l):
    return hashlib.sha1(yu.norm(l).encode()).hexdigest()[:10]


def oku(ad, o, bos):
    p = os.path.join(GD, ad + '.bin')
    try:
        return t.coz(p, o)
    except Exception:
        return bos


def yaz(ad, obj, o):
    os.makedirs(GD, exist_ok=True)
    open(os.path.join(GD, ad + '.bin'), 'wb').write(t.sifrele(obj, o))


def uygula(gun, kat, durum, stok, F, S, O):
    """Bir günlük anlık görüntüyü geçmişe işler. kat: {anahtar: [satırlar]}, durum: katalog_durum markaları, stok: {anahtar: {özet: adet}}"""
    ok_marka = {m.get('marka') for k, m in durum.items() if m.get('durum') == 'ok' and k in kat}
    simdi = set()
    marka_var = {k[0] for l, k in F.items() if not l.startswith('_')}   # ilk kez okunan markanın bütün ürünleri "yeni" sayılmaz
    for key, rows in kat.items():
        for r in rows:
            l = r.get('l'); f = r.get('f')
            if not l or not f or aksesuar(r.get('u') or ''):
                continue
            simdi.add(l); e = r.get('e') if (r.get('e') or 0) > f else None
            g = r.get('g') if isinstance(r.get('g'), str) and r.get('g', '').startswith('http') else None
            k = F.get(l)
            if not k:
                F[l] = [r.get('m'), r.get('u'), g, [[gun, f, e]], gun, gun]
                if F.get('_ilk_gun') and F['_ilk_gun'] < gun and r.get('m') in marka_var:
                    O.append([gun, 'yeni', l])
                continue
            k[0], k[1] = r.get('m'), r.get('u'); k[2] = g or k[2]
            son_f = k[3][-1][1]
            if abs(son_f - f) >= 0.5:
                k[3].append([gun, f, e]); O.append([gun, 'dus' if f < son_f else 'art', l])
            if k[5] != gun:
                onceki = k[5]
                k[5] = gun
                if onceki and onceki < F.get('_son_gun', gun) and F.get('_son_gun') != gun:
                    pass
    # stoktan çıkanlar: dün vardı, bugün yok (markanın sitesi bugün de okunduysa)
    dun = F.get('_son_gun')
    if dun and dun < gun:
        for l, k in F.items():
            if l.startswith('_'):
                continue
            if k[5] == dun and l not in simdi and k[0] in ok_marka:
                O.append([gun, 'bitti', l])
    F['_son_gun'] = gun
    F.setdefault('_ilk_gun', gun)
    for key, st in (stok or {}).items():
        for h, adet in st.items():
            if adet is None:
                continue
            s = S.setdefault(h, [])
            if not s or s[-1][0] != gun:
                s.append([gun, adet])
    sinir = (dt.date.fromisoformat(gun) - dt.timedelta(days=21)).isoformat()
    for h in list(S):
        S[h] = [x for x in S[h] if x[0] >= sinir]
        if not S[h]:
            del S[h]
    sinir45 = (dt.date.fromisoformat(gun) - dt.timedelta(days=45)).isoformat()
    O[:] = [x for x in O if x[0] >= sinir45]


def supheli_markalar():
    """Ürün başına günde 5'ten fazla satış çıkan markalar: sitedeki stok sayısı temsilî (Tudors, Madmext gibi)"""
    sup = set(SUPHE)
    try:
        adlar = json.load(open(os.path.join(DATA, 'satis_gun.json')))[-7:]
        o = t.ozel_anahtar(); top = {}
        for a in adlar:
            for r in t.coz(os.path.join(DATA, 'satis_gun', a[:-5] + '.bin'), o):
                x = top.setdefault(r['marka'], [0, 0]); x[0] += r['adet']; x[1] += r.get('urun_sayisi') or 0
        sup |= {m for m, (a, u) in top.items() if u and a / u >= 5}
    except Exception as e:
        print('satış oranı okunamadı', e)
    return sup


KALDIR = {'Tudors', 'Tommylife', 'Aura Moda'}   # takipten çıkarılan rakipler
from takip import TAKIP


def ozet(F, S, O, kat_simdi, o):
    F = {l: k for l, k in F.items() if l.startswith('_') or (k[0] in TAKIP and not aksesuar(k[1] or '') and (k[3][-1][1] or 0) >= 30)}
    O = [x for x in O if x[2] in F]
    gun = F.get('_son_gun')
    sinir = (dt.date.fromisoformat(gun) - dt.timedelta(days=7)).isoformat()
    sinir14 = (dt.date.fromisoformat(gun) - dt.timedelta(days=14)).isoformat()
    def urun(l, **ek):
        k = F.get(l)
        if not k:
            return None
        p = k[3]
        return dict(m=k[0], u=k[1], l=l, g=k[2], f=p[-1][1], e=p[-1][2], **ek)
    # fiyatı sürekli gidip gelen ürünler (varyant/kur oynaması) güvenilmez: 14 günde 3+ değişiklik
    oynak = {l for l, k in F.items() if not l.startswith('_') and sum(1 for x in k[3] if x[0] >= sinir14) >= 4}
    # bir markanın ürünlerinin çoğu oynaksa o markanın fiyat değişiklikleri hiç gösterilmez
    mt, mo = {}, {}
    for l, k in F.items():
        if l.startswith('_') or k[5] != gun:
            continue
        mt[k[0]] = mt.get(k[0], 0) + 1
        if l in oynak: mo[k[0]] = mo.get(k[0], 0) + 1
    oynak_marka = {m for m in mt if mo.get(m, 0) >= max(15, mt[m] * 0.15)}
    # bir günde ürünlerinin %25'inden fazlası "bitti" görünen marka: site o gün eksik okunmuş sayılır
    bitti_say = {}
    for g, tur, l in O:
        if tur == 'bitti' and l in F:
            bitti_say[(g, F[l][0])] = bitti_say.get((g, F[l][0]), 0) + 1
    eksik = {(g, m) for (g, m), n in bitti_say.items() if n > max(30, mt.get(m, 0) * 0.25)}
    def yuzde_gun(l, g):   # ürünün g günündeki fiyat değişimi (%)
        p = F[l][3]
        for i in range(1, len(p)):
            if p[i][0] == g and p[i - 1][1]:
                return round(100 * (p[i][1] - p[i - 1][1]) / p[i - 1][1], 1)
        return None
    # bir marka aynı gün çok sayıda ürünü AYNI fiyata çektiyse (ör. hepsi 731 ₺) bu da toplu değişikliktir
    tek = {}
    for g, tur, l in O:
        if g < sinir or tur not in ('dus', 'art') or l not in F or l in oynak:
            continue
        p = F[l][3]; yeni_f = next((x[1] for x in p if x[0] == g), None)
        if yeni_f: tek.setdefault((g, F[l][0], round(yeni_f)), set()).add(l)
    tek_l = {}
    for (g, m, f), ls in tek.items():
        if len(ls) >= 15:
            for l in ls: tek_l[(g, l)] = f
    # toplu fiyat değişikliği: bir marka aynı gün ürünlerinin çoğunun fiyatını değiştirdiyse ürün ürün değil tek satır gösterilir
    ham = {}
    for g, tur, l in O:
        if g < sinir or tur not in ('dus', 'art') or l not in F or l in oynak:
            continue
        yz = yuzde_gun(l, g)
        if yz is None or abs(yz) < 3 or abs(yz) > 80:
            continue
        ham.setdefault((g, F[l][0], tur), []).append(yz)
    toplu, toplu_k = [], set()
    for (g, m, tur), v in ham.items():
        if len(v) >= max(50, mt.get(m, 0) * 0.3):
            toplu_k.add((g, m, tur))
            v2 = sorted(v); toplu.append(dict(gun=g, m=m, tur=tur, n=len(v), orta=v2[len(v2) // 2]))
    toplu.sort(key=lambda x: (x['gun'], x['n']), reverse=True)
    dus, art, bitti, yeni_say, gunluk = [], [], [], {}, {}
    for l, k in F.items():
        if l.startswith('_') or l in oynak or k[0] in oynak_marka or k[5] != gun:
            continue
        p = k[3]
        if len(p) < 2 or p[-1][0] < sinir:
            continue
        onceki = next((x[1] for x in reversed(p[:-1]) if True), None)
        simdi = p[-1][1]
        if not onceki:
            continue
        yz = round(100 * (simdi - onceki) / onceki, 1)
        if abs(yz) < 3 or abs(yz) > 80:
            continue
        if (p[-1][0], k[0], 'dus' if yz < 0 else 'art') in toplu_k or (p[-1][0], l) in tek_l:
            continue
        u = urun(l, tarih=p[-1][0], onceki=onceki, yeni=simdi, yuzde=yz)
        (dus if yz < 0 else art).append(u)
    for g, tur, l in O:
        if g < sinir or l not in F:
            continue
        m = F[l][0]
        if tur == 'bitti':
            if (g, m) in eksik or l in [x for x in ()]:
                continue
            if F[l][5] != gun:   # bugün de yok (geri gelmedi)
                u = urun(l, tarih=g)
                if u: bitti.append(u)
            gunluk.setdefault(g, {'dus': 0, 'art': 0, 'yeni': 0, 'bitti': 0})['bitti'] += 1
        elif tur == 'yeni':
            yeni_say[m] = yeni_say.get(m, 0) + 1
            gunluk.setdefault(g, {'dus': 0, 'art': 0, 'yeni': 0, 'bitti': 0})['yeni'] += 1
        elif l not in oynak and m not in oynak_marka and (g, m, tur) not in toplu_k:
            yz = yuzde_gun(l, g)
            if yz is not None and 3 <= abs(yz) <= 80 and (g, l) not in tek_l:
                gunluk.setdefault(g, {'dus': 0, 'art': 0, 'yeni': 0, 'bitti': 0})[tur] += 1
    def tekil(xs):   # aynı ürünün renkleri tek satır
        d = {}
        for x in xs:
            d.setdefault((x['m'], x['u'], x.get('yeni')), x)
        return list(d.values())
    dus = sorted(tekil(dus), key=lambda x: x['yuzde'])[:300]
    art = sorted(tekil(art), key=lambda x: -x['yuzde'])[:300]
    bitti = sorted(tekil(bitti), key=lambda x: x['tarih'], reverse=True)[:300]
    # hızla tükenenler: son 7 günde günde ortalama >= 1 satan ve stoğu 5 günden az yetecek ürünler
    sup = supheli_markalar() - KALDIR
    lmap = {lh(l): l for l, k in F.items() if not l.startswith('_') and k[5] == gun}
    hizli = []
    for h, s in S.items():
        l = lmap.get(h)
        if not l or len(s) < 3 or F[l][0] in sup:
            continue
        son7 = [x for x in s if x[0] >= sinir]
        if len(son7) < 3:
            continue
        dusus = sum(max(0, a[1] - b[1]) for a, b in zip(son7, son7[1:]) if a[1] - b[1] < 500)
        gunler = max(1, (dt.date.fromisoformat(son7[-1][0]) - dt.date.fromisoformat(son7[0][0])).days)
        gs = dusus / gunler; stok = son7[-1][1]
        if 1 <= gs <= 60 and 0 < stok <= gs * 5:
            hizli.append(urun(l, stok=stok, gunluk=round(gs, 1), kalan_gun=round(stok / gs, 1)))
    hizli = sorted(tekil([x for x in hizli if x]), key=lambda x: (x['kalan_gun'], -x['gunluk']))[:200]
    # ---- Black Friday / kampanya takibi: indirim oranı, önce zam sonra indirim ----
    def nokta(p, g):   # g gününde geçerli fiyat noktası
        v = None
        for x in p:
            if x[0] <= g: v = x
            else: break
        return v
    g14 = (dt.date.fromisoformat(gun) - dt.timedelta(days=14)).isoformat()
    g30 = (dt.date.fromisoformat(gun) - dt.timedelta(days=30)).isoformat()
    bf = {}
    for l, k in F.items():
        if l.startswith('_') or k[5] != gun or k[0] in oynak_marka or l in oynak:
            continue
        p = k[3]; f = p[-1][1]; e = p[-1][2]; m = k[0]
        b = bf.setdefault(m, {'marka': m, 'urun': 0, 'indirimli': 0, 'oranlar': [], 'once_urun': 0, 'once_indirimli': 0, 'sahte': 0, 'ornek': []})
        b['urun'] += 1
        if e and e > f:
            b['indirimli'] += 1; b['oranlar'].append(100 * (e - f) / e)
        o = nokta(p, g14)
        if o and k[4] <= g14:
            b['once_urun'] += 1
            if o[2] and o[2] > o[1]: b['once_indirimli'] += 1
        # önce zam sonra indirim: son 30 günde %8+ zam, ardından indirim; şimdiki fiyat zam öncesine göre ucuz değil
        for i in range(1, len(p)):
            if p[i][0] < g30 or not p[i - 1][1]:
                continue
            if e and e > f and p[i - 1][1] * 1.08 <= p[i][1] <= p[i - 1][1] * 1.8 and any(x[1] < p[i][1] * 0.97 for x in p[i + 1:]) and f >= p[i - 1][1] * 0.97:
                b['sahte'] += 1
                if len(b['ornek']) < 8 and not any(o_['u'] == k[1] and o_['simdi'] == f for o_ in b['ornek']):
                    b['ornek'].append(dict(m=m, u=k[1], l=l, g=k[2], once=p[i - 1][1], zam=p[i][1], simdi=f, zam_gun=p[i][0]))
                break
    bfl = []
    for m, b in bf.items():
        if b['urun'] < 10:
            continue
        o = sorted(b.pop('oranlar'))
        b['indirim_orani'] = round(100 * b['indirimli'] / b['urun']); b['ort_indirim'] = round(o[len(o) // 2]) if o else 0
        b['once_orani'] = round(100 * b['once_indirimli'] / b['once_urun']) if b['once_urun'] >= 10 else None
        b['kampanya'] = sorted({x['gun'] for x in toplu if x['m'] == m and x['tur'] == 'dus'})
        bfl.append(b)
    bfl.sort(key=lambda b: (-(b['indirim_orani'] - (b['once_orani'] or b['indirim_orani'])), -b['sahte']))
    # ---- ürün türüne göre haftalık fiyat (ortanca) ----
    haftalar = [(dt.date.fromisoformat(gun) - dt.timedelta(days=7 * i)).isoformat() for i in range(5, -1, -1)]
    haftalar = [h for h in haftalar if h >= F.get('_ilk_gun', gun)]
    tt = {}
    for l, k in F.items():
        if l.startswith('_'):
            continue
        tr = urun_turu(k[1])
        if tr in ('diger', 'aksesuar'):
            continue
        for h in haftalar:
            if k[4] <= h <= k[5]:
                v = nokta(k[3], h)
                if v: tt.setdefault(tr, {}).setdefault(h, []).append(v[1])
    tur_trend = {}
    for tr, hs in tt.items():
        sat = []
        for h in haftalar:
            v = sorted(hs.get(h, []))
            if len(v) >= 30: sat.append([h, round(v[len(v) // 2]), len(v)])
        if len(sat) >= 2: tur_trend[tr] = sat
    # ---- kaba satış göstergesi: son 7 günde stoktan çıkan ve eklenen ürün ----
    kaba = {}
    for g, tr, l in O:
        if g < sinir or l not in F or tr not in ('bitti', 'yeni'):
            continue
        m = F[l][0]
        if tr == 'bitti' and (g, m) in eksik:
            continue
        x = kaba.setdefault(m, {'bitti7': 0, 'yeni7': 0, 'urun': mt.get(m, 0)}); x[tr + '7'] += 1
    yeni_son = [urun(l) for g, tur, l in O if tur == 'yeni' and g == gun and l in F and F[l][5] == gun]
    yeni_son = tekil([x for x in yeni_son if x])
    return {'tarih': gun, 'dus': dus, 'art': art, 'bitti': bitti, 'hizli': hizli, 'yeni_marka': yeni_say, 'toplu': toplu, 'yeni_son': yeni_son[:300], 'bf': bfl, 'tur_trend': tur_trend, 'haftalar': haftalar, 'kaba': kaba,
            'oynak_marka': sorted(oynak_marka), 'supheli': sorted(sup),
            'gunluk': [dict(gun=g, **v) for g, v in sorted(gunluk.items())]}


def anlik():
    durum = json.load(open(os.path.join(DATA, 'katalog_durum.json'))).get('markalar', {})
    return durum


def katalog_oku(o, kaynak=None):
    """kaynak None: diskteki dosyalar; değilse git commit'i"""
    kat, stok = {}, {}
    if kaynak is None:
        durum = json.load(open(os.path.join(DATA, 'katalog_durum.json'))).get('markalar', {})
        for f in glob.glob(os.path.join(DATA, 'katalog', '*.bin')):
            try: kat[os.path.basename(f)[:-4]] = t.coz(f, o)
            except Exception: pass
        for f in glob.glob(os.path.join(DATA, 'satis', '*.json')):
            try: stok[os.path.basename(f)[:-5]] = json.load(open(f)).get('stok', {})
            except Exception: pass
        return durum, kat, stok
    def goster(p):
        return subprocess.run(['git', 'show', f'{kaynak}:{p}'], capture_output=True, cwd=os.path.dirname(DATA)).stdout
    durum = json.loads(goster('data/katalog_durum.json') or b'{}').get('markalar', {})
    for k in durum:
        b = goster(f'data/katalog/{k}.bin')
        if b:
            try: kat[k] = coz_bytes(b, o)
            except Exception: pass
        s = goster(f'data/satis/{k}.json')
        if s:
            try: stok[k] = json.loads(s).get('stok', {})
            except Exception: pass
    return durum, kat, stok


def coz_bytes(b, o):
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
        f.write(b); p = f.name
    try:
        return t.coz(p, o)
    finally:
        os.remove(p)


def gun_of(iso_tr):
    # katalog işi gece yarısını geçebiliyor: TR saatiyle 06:00'dan önceki çalıştırma önceki güne sayılır
    d = dt.datetime.fromisoformat(iso_tr)
    return (d - dt.timedelta(hours=6)).date().isoformat()


def main():
    o = t.ozel_anahtar()
    if '--ozet' in sys.argv:
        F = oku('fiyat', o, {}); S = oku('stok', o, {}); O = oku('olay', o, [])
        oz = ozet(F, S, O, {}, o); open(os.path.join(DATA, 'degisim.bin'), 'wb').write(t.sifrele(oz, o))
        print('özet:', oz['tarih'], 'düşen', len(oz['dus']), 'artan', len(oz['art']), 'tükenen', len(oz['bitti']), 'hızlı', len(oz['hizli']), oz['oynak_marka'], oz['supheli']); return
    if '--git' in sys.argv:
        F, S, O = {}, {}, []
        satirlar = subprocess.run(['git', 'log', '--reverse', '--format=%H %ad', '--date=iso-strict', '--', 'data/katalog_durum.json'],
                                  capture_output=True, text=True, cwd=os.path.dirname(DATA)).stdout.split('\n')
        son = {}
        for s in satirlar:
            if not s.strip():
                continue
            h, tarih = s.split(' ', 1)
            tr = dt.datetime.fromisoformat(tarih).astimezone(dt.timezone(dt.timedelta(hours=3)))
            son[gun_of(tr.replace(tzinfo=None).isoformat())] = h
        for gun in sorted(son):
            durum, kat, stok = katalog_oku(o, son[gun])
            uygula(gun, kat, durum, stok, F, S, O)
            print(gun, len(kat), 'marka', len(O), 'olay', flush=True)
    else:
        F = oku('fiyat', o, {}); S = oku('stok', o, {}); O = oku('olay', o, [])
        durum, kat, stok = katalog_oku(o)
        gun = gun_of((dt.datetime.utcnow() + dt.timedelta(hours=3)).replace(microsecond=0).isoformat())
        uygula(gun, kat, durum, stok, F, S, O)
    # 60 günden uzun süredir görülmeyen ürünler geçmişten silinir (dosya büyümesin)
    sinir = (dt.date.fromisoformat(F['_son_gun']) - dt.timedelta(days=60)).isoformat()
    for l in [l for l, k in F.items() if not l.startswith('_') and k[5] < sinir]:
        del F[l]
    yaz('fiyat', F, o); yaz('stok', S, o); yaz('olay', O, o)
    oz = ozet(F, S, O, {}, o)
    open(os.path.join(DATA, 'degisim.bin'), 'wb').write(t.sifrele(oz, o))
    print('özet:', oz['tarih'], 'düşen', len(oz['dus']), 'artan', len(oz['art']), 'tükenen', len(oz['bitti']), 'hızlı', len(oz['hizli']))


if __name__ == '__main__':
    main()
