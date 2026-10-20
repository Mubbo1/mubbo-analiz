#!/usr/bin/env python3
"""MUBBO Analiz — rakip sitelerde yeni ürün kontrolü.

GitHub Actions bunu saatte bir (ve "Run workflow" ile istendiğinde) çalıştırır.
Her rakibin ürün listesini alır (Shopify: /products.json, diğerleri: sitemap),
daha önce görülmemiş ürün adreslerini bulur, ürün sayfasından ad/fiyat/görsel
okur ve data/yeni_urunler.json dosyasına "Yeni" olarak ekler.
Sonuçlar depodaki açık anahtarla şifrelenir (scripts/acik_anahtar.pem); yalnızca
sitenin şifresini bilen okuyabilir. Gerekli paket: cryptography.
"""
import concurrent.futures as cf
import datetime as dt
import gzip
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import struct

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
RAKIPLER = [
    ["Ketench", "ketench.com"], ["UTT Basic", "uttbasic.com"], ["Ferell Moda", "ferellmoda.com"], ["Semih Kurtulmuş", "semihkurtulmusfashion.com"],
    ["Abluka Online", "ablukaonline.com.tr"], ["Aura Moda", "auramoda.com.tr"], ["Bad Bear", "badbear.com.tr"],
    ["Bpm Wear", "bpmonlinestore.com"], ["By London Butik", "bylondonbutik.com"], ["ByBasicMan", "bybasicman.com"],
    ["Bytagayman", "bytagayman.com"], ["Catch Jeans", "catch.com.tr"], ["David Gerenzo", "davidgerenzo.com"],
    ["DeepSEA", "deepsea.com.tr"], ["ErdTrend", "erdtrend.com"], ["Flaw Wear", "flawwears.com"],
    ["Forer Wear", "forerwear.com"], ["Gangown", "gangown.com.tr"], ["Giesto", "giesto.com"],
    ["Grimelange", "grimelange.com.tr"], ["Hafka Giyim", "hafkagiyim.com"], ["JuniorCrime", "juniorcrime.com"],
    ["Kaft", "kaft.com"], ["Labels Wear", "labelswearr.com"], ["Lazzy Shoes & Wear", "lzyshoes.com"],
    ["Livio Ferri", "livioferri.com.tr"], ["Madmext", "madmext.com"], ["No 362 Clo", "no362clo.com"],
    ["NOMARC", "nomarc.com.tr"], ["Outfit-Man", "outfit-man.com"], ["Papel Giyim", "papellgiyim.com"],
    ["Piedraman", "piedraman.com"], ["Respire", "respire.com.tr"], ["Slatra", "slatra.com.tr"],
    ["Streetbox", "streetbox.com.tr"], ["Studio8 Online", "studio8online.com"], ["Tarz Adam", "tarzadam.com"],
    ["Tarz Cool", "tarzcool.com"], ["Tarz Yeri", "tarzyeri.com"], ["The Champ", "thechamp.com.tr"],
    ["The Manstro", "themanstro.com"], ["Tommylife", "tommylife.com.tr"], ["Tudors", "tudors.com"],
    ["Vamos Clo", "vamosclo.com"], ["VOID TR", "voidtr.com"], ["Voltaj Giyim", "voltaj.com.tr"],
    ["Wunder", "wunder.com.tr"], ["Zaee Giyim", "zaeegiyim.com.tr"], ["Zafoni", "zafoni.com"],
]
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36'
TIMEOUT = 25
MAX_DOGRULA = 40        # bir çalışmada bir marka için açılacak en fazla yeni ürün sayfası
TASKIN = 300            # bir seferde bundan çok "yeni" adres çıkarsa site yapısı değişmiştir: sessizce taban al
KADIN = re.compile(r'kad[ıi]n|bayan|elbise|\betek\b|bluz|crop|tayt|\bbody\b|büstiyer|mad girls|\bmg\d|kız', re.I)
BUGUN = (dt.datetime.utcnow() + dt.timedelta(hours=3)).strftime('%Y-%m-%d')


def get(url, accept='*/*'):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept, 'Accept-Language': 'tr-TR,tr;q=0.9',
                                               'Accept-Encoding': 'gzip'})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        b = r.read()
        if r.headers.get('Content-Encoding') == 'gzip' or b[:2] == b'\x1f\x8b':
            b = gzip.decompress(b)
        cs = r.headers.get_content_charset() or 'utf-8'
        return b.decode(cs, 'replace'), r.geturl()


def h(url):
    return hashlib.sha1(norm(url).encode()).hexdigest()[:12]


def norm(url):
    p = urllib.parse.urlsplit(url.strip())
    host = p.netloc.lower().removeprefix('www.')
    return host + urllib.parse.unquote(p.path).rstrip('/').lower()


def fiyat(v):
    if v is None:
        return None
    s = str(v).strip().replace('TL', '').replace('₺', '').replace('\xa0', '').replace(' ', '')
    if not s:
        return None
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.') if s.rfind(',') > s.rfind('.') else s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.') if len(s.split(',')[-1]) <= 2 else s.replace(',', '')
    elif s.count('.') == 1 and len(s.split('.')[-1]) == 3:
        s = s.replace('.', '')
    try:
        f = float(re.sub(r'[^0-9.]', '', s))
        return f if f > 0 else None
    except ValueError:
        return None


# ---------- ürün listesi ----------
def shopify(host):
    out = {}
    for page in range(1, 11):
        txt, _ = get(f'https://{host}/products.json?limit=250&page={page}', 'application/json')
        ps = json.loads(txt).get('products')
        if ps is None:
            return None
        for p in ps:
            link = f'https://{host}/products/{p["handle"]}'
            vs = p.get('variants') or [{}]
            v = ([x for x in vs if x.get('available', True)] or vs)[0]
            img = (p.get('images') or [{}])
            out[link] = {'urun': p.get('title'), 'fiyat': fiyat(v.get('price')), 'stok': any(x.get('available', True) for x in vs),
                         'eski_fiyat': fiyat(v.get('compare_at_price')),
                         'gorsel': (img[0] or {}).get('src') if img else None}
        if len(ps) < 250:
            break
    return out


LOC = re.compile(r'<loc>\s*(?:<!\[CDATA\[)?\s*([^<\]\s]+)', re.I)
SKIP = re.compile(r'\.(jpe?g|png|webp|gif|svg|pdf|css|js)(\?|$)|/(blog|haber|kategori|kategoriler|category|categories|collections|marka|brand|sayfa|sayfalar|page|pages|etiket|tag|hakkimizda|iletisim|sepet|uye|hesap|login|kampanya)(/|$)', re.I)


def sitemap(host):
    seen, urls, todo = set(), set(), []
    try:
        rb, _ = get(f'https://{host}/robots.txt', 'text/plain')
        todo += re.findall(r'(?im)^\s*sitemap:\s*(\S+)', rb)
    except Exception:
        pass
    todo += [f'https://{host}/sitemap.xml', f'https://{host}/sitemap_index.xml']
    n = 0
    while todo and n < 80:
        sm = todo.pop(0)
        if sm in seen:
            continue
        seen.add(sm); n += 1
        try:
            txt, _ = get(sm, 'application/xml,text/xml')
        except Exception:
            continue
        locs = [html.unescape(x) for x in LOC.findall(txt)]
        if '<sitemapindex' in txt[:2000].lower() or (locs and all(re.search(r'\.xml(\.gz)?(\?|$)|sitemap', l, re.I) for l in locs[:5])):
            subs = locs
            pri = [l for l in subs if re.search(r'product|urun|ürün', l, re.I)]
            todo = pri + [l for l in subs if l not in pri and not re.search(r'image|blog|categor|kategori|page|brand|marka', l, re.I)] + todo
            continue
        for l in locs:
            if norm(l).split('/')[0] == host.removeprefix('www.') and not SKIP.search(l):
                urls.add(l)
    return urls


# ---------- ürün sayfası ----------
def meta(txt, *names):
    for n in names:
        m = re.search(r'<meta[^>]+(?:property|name|itemprop)=["\']' + re.escape(n) + r'["\'][^>]*content=["\']([^"\']*)', txt, re.I) \
            or re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name|itemprop)=["\']' + re.escape(n) + r'["\']', txt, re.I)
        if m and m.group(1).strip():
            return html.unescape(m.group(1).strip())
    return None


def jsonld_product(txt):
    for blk in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', txt, re.I | re.S):
        try:
            d = json.loads(blk.strip())
        except Exception:
            continue
        stack = [d]
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                stack += x
            elif isinstance(x, dict):
                t = x.get('@type')
                if t == 'Product' or (isinstance(t, list) and 'Product' in t):
                    return x
                stack += [v for k, v in x.items() if k in ('@graph', 'mainEntity', 'itemListElement')]
    return None


TUKENDI = re.compile(r'outofstock|out of stock|soldout|sold out|discontinued|t[üu]kendi|stokta yok|oos\b', re.I)


def stok_var(p, txt):
    """Ürün satışta mı? JSON-LD offers.availability ya da meta product:availability'e bakar; bilgi yoksa True."""
    of = p.get('offers') if p else None
    ofs = of if isinstance(of, list) else ([of] if isinstance(of, dict) else [])
    alt = []
    for o in ofs:
        if isinstance(o, dict) and isinstance(o.get('offers'), list):   # AggregateOffer
            alt += [x for x in o['offers'] if isinstance(x, dict)]
    ofs = alt or ofs
    av = [str(o.get('availability') or '') for o in ofs if isinstance(o, dict) and o.get('availability')]
    if av:
        return any(not TUKENDI.search(a) for a in av)
    m = meta(txt, 'product:availability', 'og:availability', 'availability')
    if m:
        return not TUKENDI.search(m)
    return True


def urun_sayfasi(url):
    txt, son = get(url, 'text/html')
    p = jsonld_product(txt)
    ad = gorsel = None; f = e = None; doviz = False; dv = None
    if p:
        ad = p.get('name')
        im = p.get('image')
        gorsel = im[0] if isinstance(im, list) and im else (im.get('url') if isinstance(im, dict) else im)
        of = p.get('offers')
        of = of[0] if isinstance(of, list) and of else of
        if isinstance(of, dict):
            f = fiyat(of.get('price') or of.get('lowPrice'))
            cur = str(of.get('priceCurrency') or '').upper()
            if cur and cur not in ('TRY', 'TL'):
                dv = (f, cur); f = None; doviz = True
    ad = ad or meta(txt, 'og:title')
    if not ad:
        m = re.search(r'<title>(.*?)</title>', txt, re.I | re.S)
        ad = html.unescape(m.group(1).strip()) if m else None
    gorsel = gorsel or meta(txt, 'og:image', 'og:image:secure_url')
    if not doviz:
        cur = (meta(txt, 'product:price:currency', 'og:price:currency') or '').upper()
        doviz = bool(cur and cur not in ('TRY', 'TL')) or '/en/' in (son or url)
    f = None if doviz else (f or fiyat(meta(txt, 'product:price:amount', 'og:price:amount', 'price')))
    if f is None and not doviz:
        m = re.search(r'itemprop=["\']price["\'][^>]*content=["\']([^"\']+)', txt, re.I)
        f = fiyat(m.group(1)) if m else None
    if f is None and not doviz:   # ErdTrend vb. ASP.NET mağazalar: <div class="fiyat2">850,00 TL</div>, eski fiyat fiyat1'de
        m = re.search(r'<div class="fiyat2">\s*([0-9][0-9.,]*)\s*TL', txt, re.I)
        if m:
            f = fiyat(m.group(1))
            m1 = re.search(r'<div class="fiyat1">\s*([0-9][0-9.,]*)\s*TL', txt, re.I)
            e1 = fiyat(m1.group(1)) if m1 else None
            e = e or (e1 if e1 and f and e1 > f else None)
    urun_mu = bool(p) or (meta(txt, 'og:type') or '').lower() in ('product', 'og:product') or f is not None
    if not urun_mu or not ad:
        return None
    ad = re.sub(r'\s*[|\-–]\s*[^|\-–]{2,40}$', '', ad.strip()) if len(ad) > 25 else ad.strip()
    if isinstance(gorsel, str) and gorsel.startswith('//'):
        gorsel = 'https:' + gorsel
    return {'urun': ad[:200], 'fiyat': f, 'eski_fiyat': e, 'doviz': dv, 'gorsel': gorsel if isinstance(gorsel, str) and gorsel.startswith('http') else None,
            'link': son or url, 'stok': stok_var(p, txt)}


# ---------- bir marka ----------
def kontrol(marka, host, eski):
    t0 = time.time()
    kaynak, liste = None, None
    try:
        liste = shopify(host)
        kaynak = 'shopify' if liste is not None else None
    except Exception:
        liste = None
    if liste is None:
        urls = sitemap(host)
        if not urls:
            raise RuntimeError('ürün listesi okunamadı (sitemap yok ya da site erişimi engelledi)')
        liste = {u: None for u in urls}; kaynak = 'sitemap'
    hs = {h(u): u for u in liste}
    yeni_adres = [] if eski is None else [u for k, u in hs.items() if k not in eski]
    not_ = ''
    if len(yeni_adres) > TASKIN:
        not_ = f'{len(yeni_adres)} yeni adres: site yapısı değişmiş olabilir, bu sefer taban alındı'
        yeni_adres = []
    bulunan = []
    for u in yeni_adres[:MAX_DOGRULA]:
        try:
            r = liste.get(u)
            if r and r.get('urun'):
                r = dict(r, link=u)
            else:
                r = urun_sayfasi(u)
            if r and r.get('stok', True) is not False:   # stokta olmayan ürün gösterilmez
                bulunan.append(dict(r, marka=marka))
        except Exception:
            continue
    # açılamayanlar bir dahaki sefere tekrar denensin diye yalnızca bakılan adresleri tabana ekle
    bakilmayan = set(h(u) for u in yeni_adres[MAX_DOGRULA:])
    taban = sorted(k for k in hs if k not in bakilmayan) if eski is not None else sorted(hs)
    if eski is not None:
        taban = sorted(set(taban) | set(eski))   # siteden kalkan ürünler tekrar gelirse "yeni" sayılmasın
    return {'marka': marka, 'host': host, 'kaynak': kaynak, 'urun_sayisi': len(liste), 'yeni': bulunan,
            'taban': taban, 'ilk': eski is None, 'not': not_, 'sure': round(time.time() - t0, 1)}


def sifrele(obj):
    acik = serialization.load_pem_public_key(open(os.path.join(ROOT, 'scripts', 'acik_anahtar.pem'), 'rb').read())
    k = AESGCM.generate_key(256); iv = os.urandom(12)
    w = acik.encrypt(k, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    veri = gzip.compress(json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode(), 9)
    return b'MB1' + struct.pack('>H', len(w)) + w + iv + AESGCM(k).encrypt(iv, veri, None)


def anahtar(host):
    return 'h' + hashlib.sha1(host.encode()).hexdigest()[:10]


def main():
    sp = os.path.join(DATA, 'yeni_state.json'); pp = os.path.join(DATA, 'yeni_parcalar.json')
    state = json.load(open(sp)) if os.path.exists(sp) else {}
    for k in [k for k in state if k != '_eklenen' and (not k.startswith('h') or '.' in k)]:   # eski biçim: site adı açık yazılı
        state[anahtar(k)] = state.pop(k)
    parcalar = json.load(open(pp)) if os.path.exists(pp) else []
    bilinen = set(state.get('_eklenen', []))
    sec = sys.argv[1:]
    hedef = [x for x in RAKIPLER if not sec or x[0] in sec or x[1] in sec]
    t0 = time.time(); durum = []; eklenen = 0; yeni_satirlar = []
    with cf.ThreadPoolExecutor(8) as ex:
        fut = {ex.submit(kontrol, m, hst, set(state[anahtar(hst)]) if anahtar(hst) in state else None): (m, hst) for m, hst in hedef}
        for f in cf.as_completed(fut):
            m, hst = fut[f]
            try:
                r = f.result()
            except Exception as e:
                durum.append({'marka': m, 'site': hst, 'durum': 'hata', 'hata': str(e)[:160]})
                print(f'HATA site {len(durum)}: {type(e).__name__}', flush=True)
                continue
            state[anahtar(hst)] = r['taban']
            yeniler = 0
            for y in r['yeni']:
                if KADIN.search(y.get('urun') or ''):
                    continue
                y['link'] = re.sub(r'(https?://[^/]+)/en/', r'\1/', y['link'])
                hk = h(y['link'])
                if hk in bilinen:
                    continue
                bilinen.add(hk)
                yeni_satirlar.append({'marka': m, 'urun': y['urun'], 'fiyat': y['fiyat'], 'eski_fiyat': y.get('eski_fiyat'),
                                      'link': y['link'], 'ilk_gorulme': BUGUN, 'durum': 'Yeni', 'gorsel': y.get('gorsel')})
                yeniler += 1
            eklenen += yeniler
            durum.append({'marka': m, 'site': hst, 'durum': 'ok', 'kaynak': r['kaynak'], 'urun_sayisi': r['urun_sayisi'],
                          'yeni': yeniler, 'ilk_tarama': r['ilk'], 'not': r['not'], 'sure': r['sure']})
    durum.sort(key=lambda x: x['marka'].lower())
    state['_eklenen'] = sorted(bilinen)
    if yeni_satirlar:
        os.makedirs(os.path.join(DATA, 'yeni'), exist_ok=True)
        ad = dt.datetime.utcnow().strftime('%Y%m%d%H%M') + '.json'
        open(os.path.join(DATA, 'yeni', ad[:-5] + '.bin'), 'wb').write(sifrele(yeni_satirlar))
        parcalar.append(ad)
        json.dump(parcalar, open(pp, 'w'))
    json.dump(state, open(sp, 'w'), separators=(',', ':'))
    open(os.path.join(DATA, 'yeni_durum.bin'), 'wb').write(sifrele({
        'son_kontrol': dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z', 'sure_sn': round(time.time() - t0),
        'eklenen': eklenen, 'markalar': durum}))
    # Herkese açık iş kayıtlarında marka adı geçmesin: yalnızca sayılar
    print(f'Bitti: {eklenen} yeni ürün, {sum(d["durum"] == "ok" for d in durum)}/{len(durum)} site okundu.')


if __name__ == '__main__':
    main()
