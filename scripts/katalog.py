#!/usr/bin/env python3
"""MUBBO Analiz — 21 rakibin tüm ürün kataloğunu (ad, güncel fiyat, eski fiyat, link) günlük yeniler.

Altyapıya göre: Ticimax ürün listesi servisi, Shopify /products.json, diğerleri site haritası +
ürün sayfası. Yalnız erkek ürünleri tutulur. Her marka data/katalog/<anahtar>.bin dosyasına
şifreli yazılır; bir marka okunamazsa ya da ürün sayısı yarıdan fazla düşerse eski dosyası korunur.
Yeni ürünlerin küçük görselleri data/kimg_ek/<tarih>.bin dosyasına eklenir.
"""
import base64, concurrent.futures as cf, datetime as dt, gzip, hashlib, html, io, json, os, re, struct, sys, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import yeni_urun as yu   # site haritası ve ürün sayfası okuyucuları

MARKALAR = [  # anahtar, marka, site, altyapı
    ('ketench', 'Ketench', 'https://ketench.com', 'ticimax'), ('uttbasic', 'UTT Basic', 'https://www.uttbasic.com', 'ticimax'), ('toriasman', 'Torias Man', 'https://toriasman.com', 'ticimax'), ('ferell', 'Ferell Moda', 'https://www.ferellmoda.com', 'ticimax'),
    ('semih', 'Semih Kurtulmuş', 'https://semihkurtulmusfashion.com', 'ticimax'), ('madmext', 'Madmext', 'https://www.madmext.com', 'ticimax'),
    ('tudors', 'Tudors', 'https://www.tudors.com', 'ticimax'), ('hafka', 'Hafka Giyim', 'https://www.hafkagiyim.com', 'ticimax'),
    ('nomarc', 'NOMARC', 'https://www.nomarc.com.tr', 'ticimax'), ('no362', 'No 362 Clo', 'https://www.no362clo.com', 'ticimax'),
    ('abluka', 'Abluka Online', 'https://www.ablukaonline.com.tr', 'ticimax'), ('grimelange', 'Grimelange', 'https://www.grimelange.com.tr', 'ticimax'),
    ('flaw', 'Flaw Wear', 'https://www.flawwears.com', 'ticimax'), ('outfitman', 'Outfit-Man', 'https://www.outfit-man.com', 'ticimax'),
    ('papel', 'Papel Giyim', 'https://www.papellgiyim.com', 'ticimax'), ('davidgerenzo', 'David Gerenzo', 'https://davidgerenzo.com', 'ticimax'),
    ('lazzy', 'Lazzy Shoes & Wear', 'https://www.lzyshoes.com', 'shopify'), ('livioferri', 'Livio Ferri', 'https://livioferri.com.tr', 'shopify'),
    ('manstro', 'The Manstro', 'https://themanstro.com', 'harita'), ('bytagayman', 'Bytagayman', 'https://bytagayman.com', 'harita'),
    ('forer', 'Forer Wear', 'https://forerwear.com', 'harita'), ('piedraman', 'Piedraman', 'https://piedraman.com', 'harita'),
    ('deepsea', 'DeepSEA', 'https://deepsea.com.tr', 'harita'),
    # 13 Ekim: kalan rakipler
    ('badbear', 'Bad Bear', 'https://www.badbear.com.tr', 'ticimax'), ('bpm', 'Bpm Wear', 'https://www.bpmonlinestore.com', 'ticimax'),
    ('labels', 'Labels Wear', 'https://www.labelswearr.com', 'ticimax'), ('respire', 'Respire', 'https://www.respire.com.tr', 'ticimax'),
    ('slatra', 'Slatra', 'https://www.slatra.com.tr', 'ticimax'), ('streetbox', 'Streetbox', 'https://www.streetbox.com.tr', 'ticimax'),
    ('tarzcool', 'Tarz Cool', 'https://www.tarzcool.com', 'ticimax'),
    ('catch', 'Catch Jeans', 'https://catch.com.tr', 'shopify'), ('giesto', 'Giesto', 'https://giesto.com', 'shopify'),
    ('juniorcrime', 'JuniorCrime', 'https://juniorcrime.com', 'shopify'), ('studio8', 'Studio8 Online', 'https://studio8online.com', 'shopify'),
    ('thechamp', 'The Champ', 'https://thechamp.com.tr', 'shopify'), ('vamos', 'Vamos Clo', 'https://vamosclo.com', 'shopify'),
    ('gangown', 'Gangown', 'https://gangown.com.tr', 'harita'), ('void', 'VOID TR', 'https://voidtr.com', 'harita'), ('wunder', 'Wunder', 'https://wunder.com.tr', 'harita'),
    ('bylondon', 'By London Butik', 'https://www.bylondonbutik.com', 'harita'), ('erdtrend', 'ErdTrend', 'https://erdtrend.com', 'harita'),
    ('kaft', 'Kaft', 'https://www.kaft.com', 'harita'), ('tarzyeri', 'Tarz Yeri', 'https://tarzyeri.com', 'harita'),
    ('tommylife', 'Tommylife', 'https://www.tommylife.com.tr', 'harita'), ('voltaj', 'Voltaj Giyim', 'https://www.voltaj.com.tr', 'harita'),
    ('zaee', 'Zaee Giyim', 'https://zaeegiyim.com.tr', 'harita'), ('zafoni', 'Zafoni', 'https://zafoni.com', 'harita'),
    ('bybasicman', 'ByBasicMan', 'https://bybasicman.com', 'trendyol:155222'), ('aura', 'Aura Moda', 'https://auramoda.com.tr', 'harita'),
]
KADIN = re.compile(r'kad[ıi]n|bayan|elbise|\betek\b|bluz|crop|tayt|\bbody\b|büstiyer|mad girls|\bmg\d|kız', re.I)
UA = yu.UA


def get(url, accept='application/json'):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept, 'Accept-Language': 'tr-TR,tr;q=0.9', 'X-Requested-With': 'XMLHttpRequest'})
    for deneme in range(3):   # zaman aşımı / geçici hata: iki kez daha dene (Madmext 21 Ekim'de zaman aşımına düştü)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
                if b[:2] == b'\x1f\x8b':
                    b = gzip.decompress(b)
                return b.decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            if e.code < 500 or deneme == 2:
                raise
        except Exception:
            if deneme == 2:
                raise
        time.sleep(5 * (deneme + 1))


def tl(s):
    return yu.fiyat(s)


def ticimax(site):
    F = {"CategoryIdList": [], "BrandIdList": [], "SupplierIdList": [], "TagIdList": [], "TagId": -1, "FilterObject": [], "MinStockAmount": -1,
         "IsShowcaseProduct": -1, "IsOpportunityProduct": -1, "FastShipping": -1, "IsNewProduct": -1, "IsDiscountedProduct": -1, "IsShippingFree": -1,
         "IsProductCombine": -1, "MinPrice": 0, "MaxPrice": 0, "SearchKeyword": "", "StrSearch": "", "StrProductIds": "", "IsSimilarProductActive": False,
         "CategoryIdSearch": -1, "IsLabelActive": False, "ShowList": 1, "LabelIds": "", "IncludeAllCategoryProducts": True}
    out, n, toplam, yabanci = [], 1, None, False
    while True:
        P = {"PageItemCount": 100, "PageNumber": n, "OrderBy": "KATEGORISIRA", "OrderDirection": "ASC"}
        u = (site + '/api/product/GetProductList?c=trtry0000&FilterJson=' + urllib.parse.quote(json.dumps(F, separators=(',', ':'))) +
             '&PagingJson=' + urllib.parse.quote(json.dumps(P, separators=(',', ':'))) + '&CreateFilter=false&TransitionOrder=0&PageType=1&PageId=0')
        d = json.loads(get(u))
        ps = d.get('products') or []
        toplam = toplam or d.get('totalProductCount')
        for p in ps:
            stokyok = not p.get('inStock', True)   # tükenenler satış tahmini için sayılır, katalogdan sonra çıkarılır
            usd = bool(re.search(r'[$€£]', str(p.get('productSellPriceStr') or '')))
            yabanci = yabanci or usd
            sell, cart, mk = tl(p.get('productSellPriceStr')), tl(p.get('productCartPriceStr')), tl(p.get('marketPriceStr'))
            if cart and sell and cart < sell:
                f, e = cart, sell
            else:
                f, e = sell, (mk if mk and sell and mk > sell else None)
            out.append({'u': p.get('name'), 'f': f, 'e': e, 'l': site + p.get('url', ''), 'gurl': urllib.parse.urljoin(site + '/', p.get('imageThumbPath') or p.get('imagePath') or '') or None, 'cat': p.get('category') or '', 'usd': usd, 'adet': 0 if stokyok else p.get('totalStockAmount'), 'stokyok': stokyok})
        if not ps or (toplam and n * 100 >= toplam) or n > 200:
            break
        n += 1
        time.sleep(0.3)
    if yabanci:
        out = kur_cevir(site, out)
    return out


def yol(l):
    p = urllib.parse.urlsplit(l).path.lower().rstrip('/')
    return p[3:] if p.startswith('/en/') else p


def refkey(site):
    k = re.sub(r'[^a-z]', '', urllib.parse.urlsplit(site).netloc.split('.')[-2] if '.' in site else site)
    if k in ('com',):
        k = re.sub(r'[^a-z]', '', urllib.parse.urlsplit(site).netloc.split('.')[-3])
    return 'ferell' if 'ferell' in k else k


def kur_cevir(site, rows):
    # GitHub sunucusu yurt dışında; site dolar gösteriyor. Sitenin kendi kurunu, fiyatı bilinen (10 Ekim TL) ürünlerden
    # hesaplayıp TL'ye çevir. Fiyatı değişmemiş ürünlerde bilinen TL fiyatı aynen kullanılır.
    key = refkey(site)
    rp = os.path.join(DATA, 'kur_ref_' + key + '.json')
    kp = os.path.join(DATA, 'kur_son.json')
    ref = json.load(open(rp))['fiyat'] if os.path.exists(rp) else {}
    hs = lambda l: hashlib.sha1(yol(l).encode()).hexdigest()[:10]
    oran = sorted(ref[hs(r['l'])] / r['f'] for r in rows if r.get('usd') and r.get('f') and hs(r['l']) in ref)
    oran = [x for x in oran if 15 < x < 120]   # makul dolar kuru aralığı
    if len(oran) >= 30:
        kur = oran[len(oran) // 2]
        json.dump({'kur': kur, 'tarih': dt.datetime.utcnow().strftime('%Y-%m-%d'), 'kaynak': key}, open(kp, 'w'))
    elif os.path.exists(kp):
        kur = json.load(open(kp))['kur']   # referansı olmayan site: başka Ticimax sitesinden bugün hesaplanan dolar kuru
    else:
        raise RuntimeError('site TL yerine yabancı para birimi gösterdi (kur referansı yok)')
    if not 15 < kur < 120:
        raise RuntimeError(f'hesaplanan kur makul değil ({kur:.2f})')
    for r in rows:
        r['l'] = site + yol(r['l'])
        if not r.get('usd'):
            continue
        for k in ('f', 'e'):
            if r.get(k):
                v = round(r[k] * kur, 2); bil = ref.get(hs(r['l'])) if k == 'f' else None
                r[k] = bil if bil and abs(bil - v) / bil < 0.006 else v
        r['kur'] = True
    print(f'  kur {kur:.4f} ({len(oran)} ürünle hesaplandı)', flush=True)
    return rows


def shopify(site):
    out = []
    for n in range(1, 60):
        ps = json.loads(get(f'{site}/products.json?limit=250&page={n}')).get('products') or []
        for p in ps:
            vs = [v for v in p.get('variants', []) if v.get('available', True)]
            if not vs:
                continue
            v = vs[0]; f = tl(v.get('price')); e = tl(v.get('compare_at_price'))
            img = (p.get('images') or [{}])[0].get('src') if p.get('images') else None
            out.append({'u': p.get('title'), 'f': f, 'e': e if e and f and e > f else None, 'l': f"{site}/products/{p['handle']}", 'gurl': img, 'cat': p.get('product_type') or ''})
        if len(ps) < 250:
            break
    return out


def harita(site):
    host = urllib.parse.urlsplit(site).netloc
    urls = sorted(yu.sitemap(host))
    out = []
    def bir(u):
        try:
            r = yu.urun_sayfasi(u)
            if not r:
                return None
            f = r['fiyat']; k = None
            if f is None and r.get('doviz') and r['doviz'][0] and r['doviz'][1] == 'USD':
                kp = os.path.join(DATA, 'kur_son.json')
                if os.path.exists(kp):   # dolar gösteren site: bugünkü kurla çevrildi (yaklaşık)
                    f = round(r['doviz'][0] * json.load(open(kp))['kur'], 2); k = True
            return {'u': r['urun'], 'f': f, 'e': r.get('eski_fiyat'), 'l': re.sub(r'(https?://[^/]+)/en/', r'\1/', r['link']), 'gurl': r.get('gorsel'), 'cat': '', 'kur': k,
                    'stokyok': r.get('stok') is False}
        except Exception:
            return None
    with cf.ThreadPoolExecutor(8) as ex:
        for r in ex.map(bir, urls[:6000]):
            if r:
                out.append(r)
    return out


def trendyol(mid):
    # Kendi sitesi açılmayan markalar: Trendyol'daki mağaza ürünleri
    out = []
    for n in range(1, 80):
        u = f'https://public.trendyol.com/discovery-web-searchgw-service/v2/api/infinite-scroll/sr?mb={mid}&pi={n}&culture=tr-TR&userGenderId=1&channelId=1'
        d = json.loads(get(u)); ps = ((d.get('result') or {}).get('products')) or []
        for p in ps:
            pr = p.get('price') or {}
            f = pr.get('discountedPrice') or pr.get('sellingPrice'); e = pr.get('originalPrice')
            img = (p.get('images') or [None])[0]
            out.append({'u': p.get('name'), 'f': f, 'e': e if e and f and e > f else None, 'l': 'https://www.trendyol.com' + p.get('url', ''),
                        'gurl': ('https://cdn.dsmcdn.com' + img) if img and img.startswith('/') else img, 'cat': p.get('categoryName') or ''})
        if len(ps) < 24:
            break
        time.sleep(0.5)
    return out


def kucuk_gorsel(url):
    from PIL import Image
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'image/*'})
    with urllib.request.urlopen(req, timeout=25) as r:
        im = Image.open(io.BytesIO(r.read())).convert('RGB')
    im.thumbnail((88, 117))
    o = io.BytesIO(); im.save(o, 'WEBP', quality=45)
    return 'data:image/webp;base64,' + base64.b64encode(o.getvalue()).decode()


def sifrele(obj):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    acik = serialization.load_pem_public_key(open(os.path.join(ROOT, 'scripts', 'acik_anahtar.pem'), 'rb').read())
    k = AESGCM.generate_key(256); iv = os.urandom(12)
    w = acik.encrypt(k, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return b'MB1' + struct.pack('>H', len(w)) + w + iv + AESGCM(k).encrypt(iv, gzip.compress(json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode(), 9), None)


def satis_tahmini(key, marka, rows, bugun):
    """Stok adedini açık veren sitelerde (Ticimax: totalStockAmount) dünkü stokla bugünkünün farkından satış tahmini.
    Stok artışları (yeni mal girişi) sayılmaz; azalış = satılan adet. data/satis/<anahtar>.json: önceki gün stokları (ürün linkinin özeti -> adet).
    data/satis_gun/<tarih>_<saat>.bin (şifreli): [{tarih, marka, adet, ciro, urun_sayisi, en_cok: [[ad, adet, fiyat], ...]}], liste: data/satis_gun.json"""
    st = {lh(r['l']): (r.get('adet'), r.get('f'), r.get('u')) for r in rows if r.get('adet') is not None}
    if len(st) < max(5, len(rows) * 0.5):
        return
    os.makedirs(os.path.join(DATA, 'satis'), exist_ok=True)
    yp = os.path.join(DATA, 'satis', key + '.json')
    once = json.load(open(yp)) if os.path.exists(yp) else None
    json.dump({'tarih': bugun, 'stok': {h: v[0] for h, v in st.items()}}, open(yp, 'w'), separators=(',', ':'))
    if not once or once.get('tarih') == bugun:
        return
    satilan = []
    for h, (adet, f, ad) in st.items():
        o = once['stok'].get(h)
        if o is not None and adet is not None and o > adet and o - adet < 500:   # 500+ ani düşüş: stok düzeltmesi sayılır
            satilan.append((ad, int(o - adet), f or 0))
    satilan.sort(key=lambda x: -x[1])
    SATIS.append({'tarih': bugun, 'onceki': once.get('tarih'), 'marka': marka, 'adet': sum(x[1] for x in satilan),
                  'ciro': round(sum(x[1] * x[2] for x in satilan)), 'urun_sayisi': len(satilan), 'en_cok': [list(x) for x in satilan[:15]]})


SATIS = []


def lh(l):
    return hashlib.sha1(yu.norm(l).encode()).hexdigest()[:10]


def main():
    bugun = (dt.datetime.utcnow() + dt.timedelta(hours=3)).strftime('%Y-%m-%d')
    dp = os.path.join(DATA, 'katalog_durum.json'); vp = os.path.join(DATA, 'kimg_var.json'); ep = os.path.join(DATA, 'kimg_ek.json')
    durum = json.load(open(dp)) if os.path.exists(dp) else {'markalar': {}}
    var = set(json.load(open(vp))) if os.path.exists(vp) else set()
    ek_liste = json.load(open(ep)) if os.path.exists(ep) else []
    os.makedirs(os.path.join(DATA, 'katalog'), exist_ok=True)
    sec = sys.argv[1:]
    yeni_gorsel = {}
    emb_is = {}   # görüntü vektörleri için iş listesi (yalnız runner'ın geçici klasörüne; depoya girmez)
    for key, marka, site, alt in MARKALAR:
        if sec and key not in sec:
            continue
        eski = durum['markalar'].get(key, {})
        t0 = time.time()
        try:
            rows = trendyol(alt.split(':')[1]) if alt.startswith('trendyol:') else {'ticimax': ticimax, 'shopify': shopify, 'harita': harita}[alt](site)
            rows = [r for r in rows if r.get('u') and r.get('l') and not KADIN.search((r.get('u') or '') + ' ' + (r.get('cat') or ''))]
            uniq = {}
            for r in rows:
                uniq.setdefault(yu.norm(r['l']), r)
            rows = list(uniq.values())
            onceki = eski.get('urun') or 0
            if not rows or (onceki and len(rows) < onceki * 0.5):
                raise RuntimeError(f'{len(rows)} ürün geldi (önceki {onceki}); eski katalog korundu')
            # stokta olmayan ürünler katalogdan çıkarılır (sayfası açılıp tükendiği görülenler; yukarıdaki kontrole sayılır)
            stokyok = sum(1 for r in rows if r.get('stokyok'))
            tum_rows = rows
            rows = [r for r in rows if not r.get('stokyok')]
            if not rows:
                raise RuntimeError('stokta ürün kalmadı görünüyor; eski katalog korundu')
            if stokyok:
                print(f'  {key}: {stokyok} stokta olmayan ürün çıkarıldı', flush=True)
            # yeni ürünlerin görselleri (en fazla 1000 / marka / gün)
            yeni = [r for r in rows if lh(r['l']) not in var and r.get('gurl')]
            def g(r):
                try:
                    return r['l'], kucuk_gorsel(r['gurl'])
                except Exception:
                    return r['l'], None
            with cf.ThreadPoolExecutor(6) as ex:
                for l, d in ex.map(g, yeni[:1000]):
                    if d:
                        yeni_gorsel[l] = d; var.add(lh(l))
            out = [dict({'m': marka, 'u': r['u'], 'f': r['f'], 'e': r['e'], 'l': r['l']}, **({'k': 1} if r.get('kur') else {}),
                        **({'g': r['gurl']} if r.get('gurl') else {})) for r in rows]
            emb_is[key] = [[r['l'], r.get('gurl')] for r in rows]
            if alt == 'ticimax' and not any(r.get('usd') for r in rows):
                # TL gelen gün: dolar gösterdiği günler için fiyat referansını tazele
                json.dump({'not': marka + ' TL fiyat referansı', 'fiyat': {hashlib.sha1(yol(r['l']).encode()).hexdigest()[:10]: r['f'] for r in rows if r.get('f')}},
                          open(os.path.join(DATA, 'kur_ref_' + refkey(site) + '.json'), 'w'))
            open(os.path.join(DATA, 'katalog', key + '.bin'), 'wb').write(sifrele(out))
            satis_tahmini(key, marka, tum_rows, bugun)
            durum['markalar'][key] = {'marka': marka, 'urun': len(out), 'tarih': bugun, 'durum': 'ok', 'sure': round(time.time() - t0), 'yeni_gorsel': len([r for r in yeni[:1000] if r['l'] in yeni_gorsel])}
            print(f'{key}: {len(out)} ürün', flush=True)
        except Exception as e:
            durum['markalar'][key] = {**eski, 'marka': marka, 'durum': 'hata', 'hata': str(e)[:160], 'hata_tarih': bugun}
            print(f'{key}: HATA {type(e).__name__} {str(e)[:100]}', flush=True)
    if yeni_gorsel:
        os.makedirs(os.path.join(DATA, 'kimg_ek'), exist_ok=True)
        ad = dt.datetime.utcnow().strftime('%Y%m%d%H%M') + '.json'
        open(os.path.join(DATA, 'kimg_ek', ad[:-5] + '.bin'), 'wb').write(sifrele(yeni_gorsel))
        ek_liste.append(ad); json.dump(ek_liste, open(ep, 'w'))
    json.dump(emb_is, open(os.environ.get('EMB_IS', '/tmp/emb_is.json'), 'w'), ensure_ascii=False)
    if SATIS:
        os.makedirs(os.path.join(DATA, 'satis_gun'), exist_ok=True)
        ad = dt.datetime.utcnow().strftime('%Y%m%d%H%M') + '.json'
        open(os.path.join(DATA, 'satis_gun', ad[:-5] + '.bin'), 'wb').write(sifrele(SATIS))
        lp = os.path.join(DATA, 'satis_gun.json'); ls = json.load(open(lp)) if os.path.exists(lp) else []
        json.dump(ls + [ad], open(lp, 'w'))
    durum['son'] = dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    json.dump(durum, open(dp, 'w'), ensure_ascii=False, indent=0)
    json.dump(sorted(var), open(vp, 'w'), separators=(',', ':'))
    print('Bitti:', sum(1 for m in durum['markalar'].values() if m.get('durum') == 'ok'), 'marka güncel,', len(yeni_gorsel), 'yeni görsel')


if __name__ == '__main__':
    main()
