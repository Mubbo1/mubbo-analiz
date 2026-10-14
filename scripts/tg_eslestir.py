#!/usr/bin/env python3
"""Telegram toptancı ürünlerini rakip kataloglarıyla eşleştirme yardımcısı (Claude kullanır).

Kullanım (depo kökünde, MUBBO_SIFRE ortam değişkeni site şifresi):
  python3 scripts/tg_eslestir.py hazirla            -> /tmp/tg/ altında bekleyen ürünler (foto + metin) ve liste
  python3 scripts/tg_eslestir.py aday ID --tur "triko,kazak" [--renk lacivert] [--kelime "fermuarli,yarim"] [--n 48]
                                                    -> /tmp/tg/ID/aday_1.jpg.. numaralı aday sayfaları + aday.json
  python3 scripts/tg_eslestir.py yakin ID 3,17,34  -> /tmp/tg/ID/yakin.jpg: seçilen adaylar BÜYÜK fotoğrafla, solda toptancı ürünü
  python3 scripts/tg_eslestir.py yaz sonuc.json     -> sonuçları şifreleyip data/tg_sonuc.bin'e ekler

sonuc.json: [{"id": "...", "ozet": "lacivert yarım fermuarlı triko", "tur": "triko",
              "ayni": [aday no, ...], "benzer": [aday no, ...]}]
"""
import base64, colorsys, glob, gzip, hashlib, io, json, os, re, struct, sys
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data'); WORK = '/tmp/tg'
OAEP = padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
TR = str.maketrans('ıİğĞüÜşŞöÖçÇ', 'iigguussoocc')


def fold(s):
    return re.sub(r'[^a-z0-9 ]', ' ', str(s or '').translate(TR).lower())


def ozel_anahtar():
    sifre = os.environ.get('MUBBO_SIFRE')
    if not sifre:
        sys.exit('MUBBO_SIFRE ortam değişkeni gerekli')
    kl = json.load(open(os.path.join(ROOT, 'kilit.json')))
    k = PBKDF2HMAC(hashes.SHA256(), 32, base64.b64decode(kl['salt']), kl['iter']).derive(sifre.encode())
    der = AESGCM(k).decrypt(base64.b64decode(kl['iv']), base64.b64decode(kl['ct']), None)
    return serialization.load_der_private_key(der, None)


def coz(path, ozel):
    b = open(path, 'rb').read(); n = struct.unpack('>H', b[3:5])[0]
    return json.loads(gzip.decompress(AESGCM(ozel.decrypt(b[5:5 + n], OAEP)).decrypt(b[5 + n:17 + n], b[17 + n:], None)))


def sifrele(obj, ozel):
    acik = ozel.public_key(); k = AESGCM.generate_key(256); iv = os.urandom(12)
    w = acik.encrypt(k, OAEP)
    return b'MB1' + struct.pack('>H', len(w)) + w + iv + AESGCM(k).encrypt(iv, gzip.compress(json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode(), 9), None)


def img(b64):
    if b64.startswith('data:'):
        b64 = b64.split(',', 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(b64))).convert('RGB')


def thumb_b64(im, px=260, q=70):
    im = im.copy(); im.thumbnail((px, px)); o = io.BytesIO(); im.save(o, 'JPEG', quality=q); return base64.b64encode(o.getvalue()).decode()


def urunler(ozel):
    """Telegram paylaşımlarını ürünlere grupla: aynı kanalda 3 dakikadan yakın paylaşımlar tek ürün."""
    posts = []
    for f in json.load(open(os.path.join(DATA, 'tg_parcalar.json'))):
        posts += coz(os.path.join(DATA, 'tg', f[:-5] + '.bin'), ozel)
    posts = list({(p['kanal'], p['id']): p for p in posts}.values())   # geriye dönük toplamada tekrar gelenler
    from datetime import datetime
    t = lambda p: datetime.fromisoformat(p['tarih']).timestamp() if p.get('tarih') else 0
    posts.sort(key=lambda p: (p['kanal'], p['id']))
    gr = []
    for p in posts:
        if gr and gr[-1][-1]['kanal'] == p['kanal'] and abs(t(p) - t(gr[-1][-1])) <= 180:
            gr[-1].append(p)
        else:
            gr.append([p])
    out = []
    for g in gr:
        fotos = [f for p in g for f in p.get('fotolar', [])]
        if not fotos:
            continue
        metin = '\n'.join(p['metin'] for p in g if p.get('metin')).strip()
        metin = re.sub(r'(?im)^.*(whatsapp|wp|\+90|05\d{2}).*$', '', metin).strip()   # telefon satırları
        out.append({'id': g[0]['kanal'] + '-' + str(g[0]['id']), 'kanal': g[0]['kanal'], 'baslik': g[0].get('baslik') or g[0]['kanal'],
                    'tarih': g[0]['tarih'], 'metin': metin, 'fotolar': fotos[:8], 'post': f"https://t.me/{g[0]['kanal']}/{g[0]['id']}"})
    return out


def sonuclar(ozel):
    p = os.path.join(DATA, 'tg_sonuc.bin')
    return coz(p, ozel) if os.path.exists(p) else []


def hazirla():
    ozel = ozel_anahtar(); os.makedirs(WORK, exist_ok=True)
    bitti = {r['id'] for r in sonuclar(ozel)}
    bek = sorted([u for u in urunler(ozel) if u['id'] not in bitti], key=lambda u: u['tarih'] or '', reverse=True)
    toplam = len(bek); bek = bek[:int(os.environ.get('TG_EN_COK', '40'))]   # bir çalışmada en yeni 40 ürün
    for u in bek:
        d = os.path.join(WORK, u['id']); os.makedirs(d, exist_ok=True)
        ims = [img(f) for f in u['fotolar'][:4]]
        h = 420; ims = [i.resize((max(1, int(i.width * h / i.height)), h)) for i in ims]
        c = Image.new('RGB', (sum(i.width for i in ims) + 8 * (len(ims) - 1), h), 'white'); x = 0
        for i in ims:
            c.paste(i, (x, 0)); x += i.width + 8
        c.save(os.path.join(d, 'urun.jpg'), quality=85)
        open(os.path.join(d, 'metin.txt'), 'w').write(u['metin'])
        json.dump(u, open(os.path.join(d, 'urun.json'), 'w'), ensure_ascii=False)
    json.dump([{'id': u['id'], 'toptanci': u['baslik'], 'tarih': u['tarih'], 'metin': u['metin'][:200]} for u in bek],
              open(os.path.join(WORK, 'bekleyen.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'{len(bek)} ürün bu çalışmada işlenecek (toplam bekleyen {toplam}) -> {WORK}/bekleyen.json ; her biri için {WORK}/<id>/urun.jpg')


_KAT = None


def katalog(ozel):
    global _KAT
    if _KAT is None:
        idx = []
        for f in sorted(glob.glob(os.path.join(DATA, 'katalog', '*.bin'))):   # günlük yenilenen marka katalogları
            idx += coz(f, ozel)
        if not idx:
            idx = coz(os.path.join(DATA, 'katalog_idx.bin'), ozel)
        shards = {}
        for f in glob.glob(os.path.join(DATA, 'kimg', '*.bin')) + glob.glob(os.path.join(DATA, 'kimg_ek', '*.bin')):
            shards.update(coz(f, ozel))
        for r in idx:
            r['g'] = shards.get(r['l']); r['t'] = fold(r['u'])
        # otomatik taramanın bulduğu yeni ürünler de aday olsun
        try:
            yeni = coz(os.path.join(DATA, 'yeni_urunler.bin'), ozel)
            for f in (json.load(open(os.path.join(DATA, 'yeni_parcalar.json'))) if os.path.exists(os.path.join(DATA, 'yeni_parcalar.json')) else []):
                yeni += coz(os.path.join(DATA, 'yeni', f[:-5] + '.bin'), ozel)
            seen = {r['l'] for r in idx}
            for y in yeni:
                if y.get('link') and y['link'] not in seen and y.get('durum') == 'Yeni':
                    idx.append({'m': y['marka'], 'u': y['urun'], 'f': y.get('fiyat'), 'e': y.get('eski_fiyat'), 'l': y['link'], 'g': None, 'gurl': y.get('gorsel'), 't': fold(y['urun'])})
        except Exception:
            pass
        _KAT = idx
    return _KAT


def renk_imza(im):
    im = im.resize((24, 32)).crop((6, 6, 18, 26)); h = [0.0] * 16; n = 0
    for r, g, b in list(im.getdata()):
        hh, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < 0.18 or v < 0.12:
            h[12 + min(3, int(v * 4))] += 1
        else:
            h[int(hh * 12) % 12] += 1
        n += 1
    return [x / n for x in h]


def aday(uid, tur, renk='', kelime='', n=48):
    ozel = ozel_anahtar(); kat = katalog(ozel); d = os.path.join(WORK, uid)
    turs = [fold(w).strip() for w in tur.split(',') if w.strip()]
    renks = [fold(w).strip() for w in renk.split(',') if w.strip()]
    kels = [fold(w).strip() for w in kelime.split(',') if w.strip()]
    has = lambda t, w: (' ' + t + ' ').find(' ' + w) >= 0
    havuz = [r for r in kat if r.get('g') and any(has(r['t'], w) for w in turs)] or [r for r in kat if r.get('g')]
    u = json.load(open(os.path.join(d, 'urun.json')))
    sig = renk_imza(img(u['fotolar'][0]))
    def puan(r):
        if 'h' not in r:
            try:
                r['h'] = renk_imza(img(r['g']))
            except Exception:
                r['h'] = [0] * 16
        s = sum(min(a, b) for a, b in zip(r['h'], sig)) * 4
        s += 2 * any(has(r['t'], w) for w in renks)
        s += sum(0.8 for w in kels if has(r['t'], w))
        return s
    sec = sorted(havuz, key=puan, reverse=True)[:n]
    per, cols, w, h, lab = 24, 6, 150, 200, 26
    for f in glob.glob(os.path.join(d, 'aday_*.jpg')):
        os.remove(f)
    try:
        font = ImageFont.truetype('DejaVuSans-Bold.ttf', 18)
    except Exception:
        font = ImageFont.load_default()
    for s in range(0, len(sec), per):
        part = sec[s:s + per]; rows = (len(part) + cols - 1) // cols
        c = Image.new('RGB', (cols * (w + 8) + 8, rows * (h + lab + 8) + 8), 'white'); dr = ImageDraw.Draw(c)
        for i, r in enumerate(part):
            x = 8 + (i % cols) * (w + 8); y = 8 + (i // cols) * (h + lab + 8)
            try:
                im = img(r['g']); im.thumbnail((w, h)); c.paste(im, (x + (w - im.width) // 2, y + lab + (h - im.height) // 2))
            except Exception:
                pass
            dr.rectangle([x, y, x + 44, y + lab], fill='black'); dr.text((x + 5, y + 3), str(s + i + 1), fill='white', font=font)
        c.save(os.path.join(d, f'aday_{s // per + 1}.jpg'), quality=82)
    json.dump([{'no': i + 1, 'marka': r['m'], 'urun': r['u'], 'fiyat': r['f'], 'eski_fiyat': r.get('e'), 'link': r['l']} for i, r in enumerate(sec)],
              open(os.path.join(d, 'aday.json'), 'w'), ensure_ascii=False, indent=0)
    print(f'{len(sec)} aday (havuz {len(havuz)}) -> {d}/aday_*.jpg ; numara listesi {d}/aday.json')
    for i, r in enumerate(sec):
        print(f"{i + 1}: {r['m']} · {r['u']} · {r['f']}")


def _fnv400(l):
    h = 2166136261
    b = l.encode('utf-16-le')
    for i in range(0, len(b), 2):
        h ^= b[i] | (b[i + 1] << 8); h = (h * 16777619) & 0xFFFFFFFF
    return h % 400


def yakin(uid, nos):
    ozel = ozel_anahtar(); d = os.path.join(WORK, uid)
    ad = {a['no']: a for a in json.load(open(os.path.join(d, 'aday.json')))}
    kat = {r['l']: r for r in katalog(ozel)}
    sec = [ad[int(n)] for n in nos.split(',') if n.strip() and int(n) in ad][:12]
    cache = {}
    def buyuk(l):
        n = _fnv400(l)
        if n not in cache:
            p = os.path.join(DATA, 'hb', f'{n}.bin')
            cache[n] = coz(p, ozel) if os.path.exists(p) else {}
        g = cache[n].get(l) or kat.get(l, {}).get('g')
        return img(g) if g else None
    u = img(json.load(open(os.path.join(d, 'urun.json')))['fotolar'][0])
    H = 300; u = u.resize((int(u.width * H / u.height), H))
    W = 225; cols = 4; rows = (len(sec) + cols - 1) // cols
    c = Image.new('RGB', (u.width + 16 + cols * (W + 8), max(H, rows * (H + 34)) + 8), 'white'); dr = ImageDraw.Draw(c)
    try:
        font = ImageFont.truetype('DejaVuSans-Bold.ttf', 20)
    except Exception:
        font = ImageFont.load_default()
    c.paste(u, (0, 0))
    for i, a in enumerate(sec):
        x = u.width + 16 + (i % cols) * (W + 8); y = (i // cols) * (H + 34)
        im = buyuk(a['link'])
        if im:
            im.thumbnail((W, H)); c.paste(im, (x + (W - im.width) // 2, y + 30))
        dr.rectangle([x, y, x + 50, y + 28], fill='black'); dr.text((x + 6, y + 3), str(a['no']), fill='white', font=font)
    c.save(os.path.join(d, 'yakin.jpg'), quality=85)
    print(f'{d}/yakin.jpg (solda toptancı ürünü)')
    for a in sec:
        print(f"{a['no']}: {a['marka']} · {a['urun']} · {a['fiyat']}")


def yaz(path):
    ozel = ozel_anahtar(); kat = {r['l']: r for r in katalog(ozel)}
    eski = {r['id']: r for r in sonuclar(ozel)}
    for s in json.load(open(path)):
        d = os.path.join(WORK, s['id']); u = json.load(open(os.path.join(d, 'urun.json')))
        ad = {a['no']: a for a in json.load(open(os.path.join(d, 'aday.json')))} if os.path.exists(os.path.join(d, 'aday.json')) else {}
        def es(nos, karar):
            out = []
            for no in nos:
                a = ad.get(int(no))
                if not a:
                    continue
                g = kat.get(a['link'], {}).get('g')
                out.append({**a, 'karar': karar, 'gorsel': ('data:image/jpeg;base64,' + thumb_b64(img(g), 180)) if g else kat.get(a['link'], {}).get('gurl')})
            return out
        ayni = es(s.get('ayni', []), 'ayni')
        # aynı modelin diğer renkleri (ör. Ketench (E1867), Madmext E7207 gibi model kodları)
        kod = lambda r: (re.search(r'\((E?\d{3,5})\)', r['urun']) or re.search(r'\b([A-Z]{1,3}\d{3,5})\s*$', r['urun']) or [None, None])[1]
        gor = {a['link'] for a in ayni}
        for a in list(ayni):
            k = kod(a)
            if not k:
                continue
            for r in kat.values():
                if r['m'] == a['marka'] and r['l'] not in gor and kod({'urun': r['u']}) == k:
                    gor.add(r['l']); g = r.get('g')
                    ayni.append({'no': 0, 'marka': r['m'], 'urun': r['u'], 'fiyat': r['f'], 'eski_fiyat': r.get('e'), 'link': r['l'], 'karar': 'ayni', 'renk_farkli': True,
                                 'gorsel': ('data:image/jpeg;base64,' + thumb_b64(img(g), 180)) if g else r.get('gurl')})
        eski[s['id']] = {'id': s['id'], 'kanal': u['kanal'], 'toptanci': u['baslik'], 'tarih': u['tarih'], 'metin': u['metin'], 'post': u['post'],
                        'ozet': s.get('ozet', ''), 'tur': s.get('tur', ''), 'foto': 'data:image/jpeg;base64,' + thumb_b64(img(u['fotolar'][0]), 360),
                        'fotolar': ['data:image/jpeg;base64,' + thumb_b64(img(f), 200) for f in u['fotolar'][1:4]],
                        'ayni': ayni, 'benzer': [b for b in es(s.get('benzer', []), 'benzer') if b['link'] not in gor]}
    rows = sorted(eski.values(), key=lambda r: r['tarih'] or '', reverse=True)
    open(os.path.join(DATA, 'tg_sonuc.bin'), 'wb').write(sifrele(rows, ozel))
    try:
        from datetime import datetime, timezone
        hepsi = urunler(ozel); bitti = {r['id'] for r in rows}
        open(os.path.join(DATA, 'tg_esles_durum.bin'), 'wb').write(sifrele({'zaman': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            'islenen': len(rows), 'eslesen': sum(1 for r in rows if r.get('ayni')), 'bekleyen': sum(1 for u in hepsi if u['id'] not in bitti)}, ozel))
    except Exception as e:
        print('durum yazılamadı:', e)
    print(f'tg_sonuc: {len(rows)} ürün kayıtlı')


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == 'hazirla':
        hazirla()
    elif a[0] == 'aday':
        opt = dict(zip(a[2::2], a[3::2]))
        aday(a[1], opt.get('--tur', ''), opt.get('--renk', ''), opt.get('--kelime', ''), int(opt.get('--n', 48)))
    elif a[0] == 'yakin':
        yakin(a[1], a[2])
    elif a[0] == 'yaz':
        yaz(a[1])
    else:
        sys.exit(__doc__)
