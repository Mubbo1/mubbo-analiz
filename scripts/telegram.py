#!/usr/bin/env python3
"""MUBBO Analiz — Telegram toptancı kanallarındaki yeni paylaşımları toplar.

Herkese açık kanalların web önizlemesini (t.me/s/<kanal>) okur; her paylaşımın
metnini, tarihini ve fotoğraflarını alır. Sonuçlar depodaki açık anahtarla
şifrelenir (yalnızca site şifresini bilen okuyabilir). Eşleştirmeyi (rakipte
satılıyor mu) ayrıca Claude yapar.
"""
import base64, datetime as dt, gzip, hashlib, html, io, json, os, re, struct, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
KANALLAR = ['hawkkingtoptan', 'quiikmaxx', 'HabbeeUnisex', 'hectormerter', 'PABELLONWEAR', 'savvi12', 'Dbdwk4I7aPQ2MzZk', 'quick_menn']
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36'
ILK_GUN = int(os.environ.get('GERI_GUN') or '3')   # ilk çalışmada (ya da GERI_GUN verilince) geriye kaç gün bakılsın
GERI = bool(os.environ.get('GERI_GUN'))           # geriye dönük toplama: eski paylaşımları da al
EN_COK = 400 if os.environ.get('GERI_GUN') else 80   # bir kanaldan bir seferde en fazla kaç paylaşım
FOTO_PX, FOTO_Q = 480, 72


def get(url, binary=False):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'tr-TR,tr;q=0.9'})
    with urllib.request.urlopen(req, timeout=30) as r:
        b = r.read()
        return b if binary else b.decode('utf-8', 'replace')


def temiz(s):
    s = re.sub(r'<br\s*/?>', '\n', s)
    s = re.sub(r'<[^>]+>', '', s)
    return html.unescape(s).strip()


def sayfa(kanal, before=None):
    url = f'https://t.me/s/{kanal}' + (f'?before={before}' if before else '')
    t = get(url)
    baslik = re.search(r'<meta property="og:title" content="([^"]*)"', t)
    posts = []
    for blk in re.split(r'(?=<div class="tgme_widget_message_wrap)', t)[1:]:
        m = re.search(r'data-post="([^"/]+)/(\d+)"', blk)
        if not m:
            continue
        pid = int(m.group(2))
        tm = re.search(r'<time[^>]+datetime="([^"]+)"', blk)
        tx = re.search(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', blk, re.S)
        fotos = re.findall(r"tgme_widget_message_photo_wrap[^>]*background-image:url\('([^']+)'\)", blk)
        fotos += re.findall(r"tgme_widget_message_video_thumb[^>]*background-image:url\('([^']+)'\)", blk)
        posts.append({'id': pid, 'tarih': tm.group(1) if tm else None, 'metin': temiz(tx.group(1)) if tx else '', 'foto_url': fotos})
    return (html.unescape(baslik.group(1)) if baslik else kanal), posts


def foto(url):
    from PIL import Image
    im = Image.open(io.BytesIO(get(url, True))).convert('RGB')
    im.thumbnail((FOTO_PX, FOTO_PX))
    o = io.BytesIO(); im.save(o, 'JPEG', quality=FOTO_Q, optimize=True)
    return base64.b64encode(o.getvalue()).decode()


def sifrele(obj):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    acik = serialization.load_pem_public_key(open(os.path.join(ROOT, 'scripts', 'acik_anahtar.pem'), 'rb').read())
    k = AESGCM.generate_key(256); iv = os.urandom(12)
    w = acik.encrypt(k, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    veri = gzip.compress(json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode(), 9)
    return b'MB1' + struct.pack('>H', len(w)) + w + iv + AESGCM(k).encrypt(iv, veri, None)


def anahtar(k):
    return 't' + hashlib.sha1(k.lower().encode()).hexdigest()[:10]


def main():
    sp = os.path.join(DATA, 'tg_state.json'); pp = os.path.join(DATA, 'tg_parcalar.json')
    state = json.load(open(sp)) if os.path.exists(sp) else {}
    parcalar = json.load(open(pp)) if os.path.exists(pp) else []
    sinir = (dt.datetime.utcnow() - dt.timedelta(days=ILK_GUN)).isoformat()
    toplanan, durum = [], []
    for i, k in enumerate(KANALLAR, 1):
        key = anahtar(k); son_kayit = state.get(key, {}).get('son', 0); son = 0 if GERI else son_kayit
        try:
            baslik, posts = sayfa(k)
            if not posts:
                raise RuntimeError('kanal önizlemesi boş (kanal özel ya da link yanlış olabilir)')
            hepsi = list(posts)
            while len(hepsi) < EN_COK:
                eski = min(p['id'] for p in hepsi)
                if son and eski <= son + 1:
                    break
                if not son and min((p['tarih'] or '9') for p in hepsi) < sinir:
                    break
                _, daha = sayfa(k, eski)
                daha = [p for p in daha if p['id'] < eski]
                if not daha:
                    break
                hepsi += daha
                time.sleep(1)
            yeni = sorted({p['id']: p for p in hepsi if p['id'] > son and (son or (p['tarih'] or '') >= sinir)}.values(), key=lambda p: p['id'])[-EN_COK:]
            for p in yeni:
                p['kanal'] = k; p['baslik'] = baslik
                p['fotolar'] = []
                for u in p.pop('foto_url')[:4]:
                    try:
                        p['fotolar'].append(foto(u))
                    except Exception:
                        pass
            yeni = [p for p in yeni if p['fotolar'] or p['metin']]
            toplanan += yeni
            if hepsi:
                state[key] = {'son': max([son_kayit] + [p['id'] for p in hepsi]), 'baslik_h': hashlib.sha1(baslik.encode()).hexdigest()[:6]}
            durum.append({'kanal': k, 'baslik': baslik, 'durum': 'ok', 'yeni': len(yeni)})
            print(f'kanal {i}: {len(yeni)} yeni paylaşım', flush=True)
        except Exception as e:
            durum.append({'kanal': k, 'durum': 'hata', 'hata': str(e)[:160]})
            print(f'kanal {i}: HATA {type(e).__name__}', flush=True)
    if toplanan:
        os.makedirs(os.path.join(DATA, 'tg'), exist_ok=True)
        ad = dt.datetime.utcnow().strftime('%Y%m%d%H%M') + '.json'
        open(os.path.join(DATA, 'tg', ad[:-5] + '.bin'), 'wb').write(sifrele(toplanan))
        parcalar.append(ad)
        json.dump(parcalar, open(pp, 'w'))
    json.dump(state, open(sp, 'w'), separators=(',', ':'))
    open(os.path.join(DATA, 'tg_durum.bin'), 'wb').write(sifrele({'son_kontrol': dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z', 'kanallar': durum}))
    print(f'Bitti: {len(toplanan)} paylaşım toplandı.')


if __name__ == '__main__':
    main()
