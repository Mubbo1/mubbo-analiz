#!/usr/bin/env python3
"""Rakip ürün fotoğraflarının görüntü vektörlerini (gömme) üretir; sitedeki fotoğrafla arama bunları kullanır.

katalog.py çalışırken runner'ın geçici klasörüne (/tmp/emb_is.json) {marka_anahtarı: [[link, görsel_url], ...]}
yazar. Bu betik her marka için data/emb/<anahtar>.bin dosyasını günceller:
  'EMB1' + boyut (uint16, BE) + kayıtlar: sha1(link)[:8] (8 bayt) + boyut kadar int8 (birim vektör × 127)
Katalogdan çıkan ürünler dosyadan atılır, yeni ürünler eklenir. Süre sınırı aşılırsa kalanlar ertesi güne kalır.
Vektörler yalnız ürün fotoğraflarının sayısal özetidir; link ya da ad içermez.
"""
import concurrent.futures as cf
import hashlib
import io
import json
import os
import struct
import sys
import time
import urllib.request

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
EMB = os.path.join(DATA, 'emb')
MODEL = os.path.join(ROOT, 'model', 'gorsel.onnx')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
BOY = 224


def hsh(l):
    return hashlib.sha1(l.encode()).digest()[:8]


def oku(key):
    p = os.path.join(EMB, key + '.bin')
    if not os.path.exists(p):
        return None, {}
    b = open(p, 'rb').read()
    if b[:4] != b'EMB1':
        return None, {}
    dim = struct.unpack('>H', b[4:6])[0]; n = 8 + dim; out = {}
    for i in range(6, len(b), n):
        out[b[i:i + 8]] = b[i + 8:i + n]
    return dim, out


def yaz(key, dim, kayit):
    os.makedirs(EMB, exist_ok=True)
    with open(os.path.join(EMB, key + '.bin'), 'wb') as f:
        f.write(b'EMB1' + struct.pack('>H', dim))
        for h in sorted(kayit):
            f.write(h + kayit[h])


def on_isle(veri):
    from PIL import Image
    im = Image.open(io.BytesIO(veri)).convert('RGB')
    w, h = im.size; r = BOY / min(w, h)
    im = im.resize((max(BOY, round(w * r)), max(BOY, round(h * r))), Image.BICUBIC)
    w, h = im.size; x = (w - BOY) // 2; y = (h - BOY) // 2
    im = im.crop((x, y, x + BOY, y + BOY))
    a = (np.asarray(im, dtype=np.float32) / 255.0 - MEAN) / STD
    return a.transpose(2, 0, 1)


def indir(url):
    if not url:
        return None
    if url.startswith('//'):
        url = 'https:' + url
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'image/*'})
        with urllib.request.urlopen(req, timeout=25) as r:
            return on_isle(r.read())
    except Exception:
        return None


class Model:
    def __init__(self):
        import onnxruntime as ort
        so = ort.SessionOptions(); so.intra_op_num_threads = os.cpu_count() or 4
        self.s = ort.InferenceSession(MODEL, so, providers=['CPUExecutionProvider'])
        self.inp = self.s.get_inputs()[0].name
        outs = [o.name for o in self.s.get_outputs()]
        self.out = 'image_embeds' if 'image_embeds' in outs else outs[0]

    def __call__(self, batch):
        v = self.s.run([self.out], {self.inp: np.stack(batch).astype(np.float32)})[0]
        if v.ndim == 3:
            v = v[:, 0]
        v = v / np.linalg.norm(v, axis=1, keepdims=True)
        return np.clip(np.round(v * 127), -127, 127).astype(np.int8)


def main():
    is_dosya = sys.argv[1] if len(sys.argv) > 1 else '/tmp/emb_is.json'
    sure = float(os.environ.get('EMB_SURE', '120')) * 60
    if not os.path.exists(is_dosya) or not os.path.exists(MODEL):
        print('iş listesi ya da model yok'); return
    isler = json.load(open(is_dosya))
    t0 = time.time(); m = Model(); toplam = 0; kalan_toplam = 0
    # önce en az vektörü olan markalar (ilk günlerde tüm markalar sırayla dolsun)
    sira = sorted(isler, key=lambda k: len(oku(k)[1]) / max(1, len(isler[k])))
    for key in sira:
        dim, kayit = oku(key)
        guncel = {hsh(l): (l, u) for l, u in isler[key]}
        kayit = {h: v for h, v in kayit.items() if h in guncel}
        eksik = [(h, u) for h, (l, u) in guncel.items() if h not in kayit and u]
        yeni = 0
        with cf.ThreadPoolExecutor(16) as ex:
            for i in range(0, len(eksik), 64):
                if time.time() - t0 > sure:
                    break
                parca = eksik[i:i + 64]
                ar = list(ex.map(lambda x: indir(x[1]), parca))
                ok = [(h, a) for (h, _), a in zip(parca, ar) if a is not None]
                if not ok:
                    continue
                v = m([a for _, a in ok])
                dim = v.shape[1]
                for (h, _), row in zip(ok, v):
                    kayit[h] = row.tobytes()
                yeni += len(ok)
        if dim:
            yaz(key, dim, kayit)
        kalan = len([1 for h in guncel if h not in kayit])
        kalan_toplam += kalan; toplam += yeni
        print(f'{key}: {len(kayit)} vektör (+{yeni}), eksik {kalan}', flush=True)
    durum = {'son': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'yeni': toplam, 'eksik': kalan_toplam,
             'markalar': {k: len(oku(k)[1]) for k in isler}}
    json.dump(durum, open(os.path.join(DATA, 'emb_durum.json'), 'w'), ensure_ascii=False)
    print('bitti:', toplam, 'yeni vektör,', kalan_toplam, 'eksik', f'{(time.time() - t0) / 60:.1f} dk')


if __name__ == '__main__':
    main()
