#!/usr/bin/env python3
"""Telegram toptancı ürünlerini rakip kataloglarıyla OTOMATİK eşleştirir (Claude kullanmaz, GitHub'da ücretsiz çalışır).

Yöntem: toptancı fotoğraflarının görüntü vektörü (model/gorsel.onnx, sitedeki fotoğrafla aramayla aynı model) rakip
ürünlerin vektörleriyle (data/emb) karşılaştırılır. Toptancı metninden ürün türü (kaban, tişört...) çıkarılabiliyorsa
yalnız o türdeki ürünler aday olur. Benzerlik AYNI eşiğini geçen ürün "aynı", BENZER eşiğini geçen ilk 6 "benzer" sayılır.
Sonuçlar tg_eslestir.yaz() ile sitedeki dosyalara yazılır.

Kullanım: MUBBO_SIFRE=... python3 scripts/tg_otomatik.py [--kalibre]
  --kalibre: daha önce Claude'un karar verdiği ürünlerle eşikleri dener, hiçbir dosya yazmaz.
"""
import base64, glob, hashlib, io, json, os, struct, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_eslestir as tg
import gomme
from artifact_tel import tur as urun_turu

DATA = tg.DATA
AYNI = float(os.environ.get('TG_AYNI', '1.01'))   # varsayılan: otomatik "aynı" kararı yok; aynı kararını Claude istenince verir
BENZER = float(os.environ.get('TG_BENZER', '0.70'))
YAKIN = {'kaban': {'trenckot', 'mont'}, 'trenckot': {'kaban'}, 'mont': {'kaban', 'ceket'}, 'ceket': {'mont'}, 'hirka': {'kazak'},
         'kazak': {'hirka'}, 'tisort': {'polo'}, 'polo': {'tisort'}, 'jean': {'pantolon'}, 'pantolon': {'jean'}, 'esofman': {'takim'}, 'takim': {'esofman'}}


def emb_oku():
    v = {}
    for f in glob.glob(os.path.join(DATA, 'emb', '*.bin')):
        b = open(f, 'rb').read()
        if b[:4] != b'EMB1':
            continue
        dim = struct.unpack('>H', b[4:6])[0]; n = (len(b) - 6) // (8 + dim)
        a = np.frombuffer(b, dtype=np.uint8, count=n * (8 + dim), offset=6).reshape(n, 8 + dim)
        for row in a:
            v[bytes(row[:8])] = row[8:].view(np.int8)
    return v


def havuz(ozel):
    kat = tg.katalog(ozel); vek = emb_oku(); rows, mat = [], []
    for r in kat:
        x = vek.get(gomme.hsh(r['l']))
        if x is None:
            continue
        r['k'] = urun_turu(r['u']); rows.append(r); mat.append(x)
    m = np.stack(mat).astype(np.float32) / 127.0
    m /= np.linalg.norm(m, axis=1, keepdims=True)
    return rows, m


def foto_vektor(model, fotolar):
    arr = []
    for f in fotolar[:4]:
        try:
            veri = base64.b64decode(f.split(',', 1)[1]) if f.startswith('data:') else base64.b64decode(f)
            arr.append(gomme.on_isle(veri))
        except Exception:
            pass
    if not arr:
        return None
    v = model(arr).astype(np.float32) / 127.0
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def ara(model, rows, mat, fotolar, metin):
    q = foto_vektor(model, fotolar)
    if q is None:
        return None, []
    sim = (mat @ q.T).max(axis=1)          # toptancının fotoğraflarından en iyi eşleşeni
    k = urun_turu(metin or '')
    if k not in ('diger', 'aksesuar'):
        izin = {k} | YAKIN.get(k, set())
        maske = np.array([r['k'] in izin for r in rows])
        if maske.sum() >= 5:
            sim = np.where(maske, sim, -1)
    sira = np.argsort(-sim)[:40]
    return (k if k not in ('diger', 'aksesuar') else ''), [(float(sim[i]), rows[i]) for i in sira if sim[i] > 0]


def kalibre():
    ozel = tg.ozel_anahtar(); rows, mat = havuz(ozel); model = gomme.Model()
    linkler = {r['l'] for r in rows}
    sonuc = tg.sonuclar(ozel); poz, neg = [], []
    for s in sonuc:
        _, ad = ara(model, rows, mat, [s['foto']] + s.get('fotolar', []), s.get('metin', '') + ' ' + s.get('ozet', ''))
        if not ad:
            continue
        hedef = {a['link'] for a in s.get('ayni', []) if a['link'] in linkler}
        en = ad[0][0]
        if hedef:
            sh = max((sm for sm, r in ad if r['l'] in hedef), default=0)
            sira = next((i for i, (sm, r) in enumerate(ad) if r['l'] in hedef), 99)
            poz.append((sh, sira, en)); print(f"AYNI  hedef={sh:.3f} sıra={sira} en_iyi={en:.3f} {s.get('ozet', '')[:50]}")
        elif not s.get('ayni'):
            neg.append(en)
    neg = np.array(neg)
    print(f'\n{len(poz)} aynı örnek, {len(neg)} aynısı olmayan örnek')
    for e in (0.85, 0.88, 0.9, 0.92, 0.93, 0.94, 0.95, 0.96):
        dogru = sum(1 for sh, sira, en in poz if sira == 0 and sh >= e)
        print(f'eşik {e:.2f}: aynılar bulunur {dogru}/{len(poz)} · aynısı yokken yanlışlıkla "aynı" der {int((neg >= e).sum())}/{len(neg)}')


def main():
    ozel = tg.ozel_anahtar(); rows, mat = havuz(ozel); model = gomme.Model()
    tg.hazirla()
    bek = json.load(open(os.path.join(tg.WORK, 'bekleyen.json')))
    out = []
    for b in bek:
        d = os.path.join(tg.WORK, b['id']); u = json.load(open(os.path.join(d, 'urun.json')))
        k, ad = ara(model, rows, mat, u['fotolar'], u['metin'])
        sec = [(s, r) for s, r in ad if s >= BENZER][:12]
        json.dump([{'no': i + 1, 'marka': r['m'], 'urun': r['u'], 'fiyat': r['f'], 'eski_fiyat': r.get('e'), 'link': r['l'], 'benzerlik': round(s, 3)}
                   for i, (s, r) in enumerate(sec)], open(os.path.join(d, 'aday.json'), 'w'), ensure_ascii=False)
        ayni = [i + 1 for i, (s, r) in enumerate(sec) if s >= AYNI][:3]
        benzer = [i + 1 for i in range(len(sec)) if i + 1 not in ayni][:6]
        out.append({'id': b['id'], 'ozet': (u['metin'] or '').split('\n')[0][:80], 'tur': k, 'ayni': ayni, 'benzer': benzer})
        print(b['id'], k or '-', 'aynı', len(ayni), 'benzer', len(benzer), f"en iyi {ad[0][0]:.3f}" if ad else '')
    p = os.path.join(tg.WORK, 'sonuc.json'); json.dump(out, open(p, 'w'), ensure_ascii=False)
    if out:
        tg.yaz(p)
    print(f'{len(out)} ürün işlendi, {sum(1 for o in out if o["ayni"])} tanesinde rakipte aynısı bulundu')


if __name__ == '__main__':
    kalibre() if '--kalibre' in sys.argv else main()
