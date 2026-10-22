#!/usr/bin/env python3
"""Fiyat karşılaştırma sayfasının TELEFON yolu için veri üretir.
Telefondaki Claude uygulaması sayfanın dosyalarını indiremiyor; yalnız sayfaya gömülü veri ve sayfa veritabanı (db) çalışıyor.
- kat.json: sayfaya gömülecek yazı kataloğu {anahtar: [[ad, fiyat, eski, link, tür, parça]]} (yalnız stoktakiler)
- g/<parça>.json: db'ye yazılacak küçük görseller {"a": [[link, dataURL], ...]} (her biri < 240 KB, türe göre gruplu)
Ürün türü, adda geçen SON tür kelimesidir (Türkçe adlarda tür sondadır: "Siyah Kaşe Kaban", "Polo Yaka Tişört").
Kullanım: MUBBO_SIFRE=... python3 scripts/artifact_tel.py <çıktı klasörü> [--tam]   (--tam: bütün görselleri baştan parçala)
"""
import base64, glob, hashlib, io, json, os, re, sys, unicodedata
import datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_eslestir as t
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); DATA = os.path.join(ROOT, 'data')
TUR = [  # (tür, kelimeler) — kelime başı eşleşir, en fazla 3 harf ek
    ('trenckot', ['trenckot', 'trench', 'trenc', 'pardesu']),
    ('kaban', ['kaban', 'palto', 'coat', 'overcoat']),
    ('mont', ['mont', 'parka', 'puffer', 'sisme', 'yagmurluk', 'ruzgarlik', 'windbreaker', 'anorak']),
    ('yelek', ['yelek', 'vest', 'gilet']),
    ('ceket', ['ceket', 'blazer', 'bomber', 'jacket', 'shacket', 'overshirt']),
    ('hirka', ['hirka', 'cardigan']),
    ('kazak', ['kazak', 'triko', 'sweater', 'balikci', 'knitwear', 'pullover']),
    ('sweatshirt', ['sweatshirt', 'sweat', 'hoodie', 'hoody', 'hood']),
    ('polo', ['polo']),
    ('tisort', ['tisort', 'tshirt', 't shirt', 'tee', 'atlet', 'tank', 'long sleeve', 'jersey']),
    ('gomlek', ['gomlek', 'shirt']),
    ('esofman', ['esofman', 'tracksuit', 'sweatpants']),
    ('takim', ['takim', 'set']),
    ('jean', ['jean', 'jeans', 'kot', 'denim']),
    ('sort', ['sort', 'bermuda', 'shorts', 'short', 'mayo', 'swim', 'jort']),
    ('pantolon', ['pantolon', 'trousers', 'pants', 'chino', 'kargo', 'jogger', 'cargo', 'salvar']),
    ('ayakkabi', ['ayakkabi', 'sneaker', 'bot', 'boots', 'loafer', 'terlik', 'shoes']),
]
TR = str.maketrans('çğıöşüâîû', 'cgiosuaiu')
def fold(s):
    s = (s or '').replace('İ', 'i').replace('I', 'ı').lower().translate(TR)
    s = unicodedata.normalize('NFKD', s); s = ''.join(c for c in s if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', s).split())
# Aksesuar (çorap, iç çamaşırı, çanta, kemer, takı, şapka...): sitedeki site_shim.js ile aynı kural; adın SON tür kelimesi aksesuarsa
AKS = re.compile('(^| )(corap\\w*|socks?|kilot\\w*|kulot\\w*|boxers?|bralette|briefs?|bikini|sutyen\\w*|canta\\w*|bags?|backpack|sirt cantas\\w*|kemer\\w*|belts?|cuzdan\\w*|wallets?|kartlik\\w*|kravat\\w*|papyon\\w*|atki\\w*|sal|sali|bere\\w*|beanie|sapka\\w*|hats?|caps?|kep|bone|eldiven\\w*|gloves?|kolye\\w*|necklace|bileklik\\w*|bracelet|yuzuk\\w*|kupe\\w*|earrings?|gozlu\\w*|sunglasses|parfum\\w*|perfume|fragrance|saat|saati|watches|anahtarlik\\w*|keychain|kol dugme\\w*|kravat igne\\w*|igne\\w*|mendil\\w*|havlu\\w*|towel|bandana|toka|sticker|poster|kupa|mug|kilif\\w*|maske|semsiye\\w*|hediye kart\\w*|gift card|kolonya|deodorant)(?= |$)')
GIY = re.compile('(^| )(pantolon\\w*|jeans?|kot|denim|sort\\w*|bermuda|tisort\\w*|t shirt\\w*|tshirt\\w*|gomlek\\w*|shirts?|sweat\\w*|hoodie|kazak\\w*|triko\\w*|hirka\\w*|cardigan|ceket\\w*|jacket|blazer|bomber|mont\\w*|parka|kaban\\w*|palto\\w*|coat|trenc\\w*|yelek\\w*|vest|esofman\\w*|takim\\w*|polo\\w*|ayakkabi\\w*|sneakers?|bot|botu|loafer|terlik\\w*|jogger\\w*|trousers|pants|overshirt|jorts?|salvar\\w*|atlet\\w*|tracksuit|t)(?= |$)')
def aksesuar(ad):
    t0 = fold(ad); a = [m.start() for m in AKS.finditer(t0)]; g = [m.start() for m in GIY.finditer(t0)]
    return bool(a) and a[-1] > (g[-1] if g else -1)
RX = [(k, re.compile(r'(?:^| )(' + '|'.join(re.escape(w) for w in ws) + r')[a-z]{0,3}(?= |$)')) for k, ws in TUR]
def tur(ad):
    if aksesuar(ad): return 'aksesuar'
    t0 = fold(ad); best, pos = '', -1
    for k, rx in RX:
        for m in rx.finditer(t0):
            if m.start(1) > pos: best, pos = k, m.start(1)
    # "t shirt": shirt kelimesi tişört sayılır
    if best == 'gomlek' and re.search(r'(^| )t shirt', t0): best = 'tisort'
    if not best and re.search(r' t$', t0): best = 'tisort'   # "VOID PREMIUM OVERSIZE T"
    return best or 'diger'

def kucuk(du):
    try:
        im = Image.open(io.BytesIO(base64.b64decode(du.split(',', 1)[1]))).convert('RGB')
        im.thumbnail((64, 96), Image.LANCZOS)
        b = io.BytesIO(); im.save(b, 'WEBP', quality=55, method=6)
        return 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode()
    except Exception:
        return None

def main(out):
    os.makedirs(os.path.join(out, 'g'), exist_ok=True)
    o = t.ozel_anahtar(); img = {}
    for f in glob.glob(os.path.join(DATA, 'kimg', '*.bin')) + glob.glob(os.path.join(DATA, 'kimg_ek', '*.bin')):
        try: img.update(t.coz(f, o))
        except Exception as e: print('görsel okunamadı', f, e)
    durum = json.load(open(os.path.join(DATA, 'katalog_durum.json'))).get('markalar', {})
    sinir = (dt.datetime.utcnow() - dt.timedelta(days=1)).strftime('%Y-%m-%d')
    kat, gruplar = {}, {}
    for f in sorted(glob.glob(os.path.join(DATA, 'katalog', '*.bin'))):
        key = os.path.basename(f)[:-4]; m = durum.get(key) or {}
        if not (m.get('durum') == 'ok' or (m.get('tarih') or '') >= sinir): print('atlandı', key); continue
        try: rows = t.coz(f, o)
        except Exception as e: print('okunamadı', key, e); continue
        satir = []
        for r in rows:
            if not r.get('l') or not r.get('u'): continue
            k = tur(r['u']); x = [r['u'], r.get('f'), r.get('e'), r['l'], k, '']
            if r['l'] in img: gruplar.setdefault(k, []).append((r['l'], x))
            satir.append(x)
        if satir: kat[key] = satir
    # Görsel parçaları: önceki haftalarda db'ye yazılmış ürünler aynı parçada kalır (yeniden yüklenmez);
    # yalnız yeni ürünler yeni parçalara (<tür>_y<tarih>_<n>) yazılır. Eşleme: data/tel_parca.bin (şifreli)
    yol = os.path.join(DATA, 'tel_parca.bin')
    try: eski = t.coz(yol, o)
    except Exception: eski = {}
    tam = '--tam' in sys.argv
    if tam: eski = {}
    etiket = '' if tam else 'y' + dt.datetime.utcnow().strftime('%m%d') + '_'
    yeni_harita, say = {}, {}
    for k, lst in sorted(gruplar.items()):
        yeniler = []
        for l, x in lst:
            if l in eski: x[5] = eski[l]; yeni_harita[l] = eski[l]
            else: yeniler.append((l, x))
        yeniler.sort(key=lambda z: hashlib.md5(z[0].encode()).hexdigest())
        n, cur, boy = 0, [], 0
        def yaz():
            nonlocal n, cur, boy
            if cur: json.dump({'a': cur}, open(os.path.join(out, 'g', f'{k}_{etiket}{n}.json'), 'w'), separators=(',', ':')); n += 1; cur, boy = [], 0
        bekleyen = []
        for l, x in yeniler:
            g = kucuk(img[l])
            if not g: continue
            if boy + len(g) + len(l) > 235_000:
                yaz(); bekleyen = []
            cur.append([l, g]); boy += len(g) + len(l) + 8; x[5] = f'{k}_{etiket}{n}'; yeni_harita[l] = x[5]
        yaz(); say[k] = n
    open(yol, 'wb').write(t.sifrele(yeni_harita, o))
    json.dump(kat, open(os.path.join(out, 'kat.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
    toplam = sum(len(v) for v in kat.values())
    from collections import Counter
    c = Counter(x[4] for v in kat.values() for x in v)
    print(toplam, 'ürün', dict(c.most_common())); print('yeni parça', say, sum(say.values()))

if __name__ == '__main__':
    main(next((a for a in sys.argv[1:] if not a.startswith('--')), '/tmp/tel'))
