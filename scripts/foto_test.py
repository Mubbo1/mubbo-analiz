#!/usr/bin/env python3
"""Fotoğrafla aramanın doğruluk testi: örnek ürünlerin fotoğrafını (ve ürün sayfasındaki başka bir fotoğrafını)
bozup tüm rakip vektörleri içinde arar; doğru ürünün kaçıncı çıktığını yazar."""
import io, json, os, re, sys, glob, urllib.request
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gomme as g, yeni_urun as yu
from PIL import Image, ImageOps
ROOT = g.ROOT
ornek = json.load(open(os.path.join(ROOT, 'data', 'foto_ornek.json')))
H, V, K = [], [], []
for f in sorted(glob.glob(os.path.join(g.EMB, '*.bin'))):
    dim, kay = g.oku(os.path.basename(f)[:-4])
    for h, v in kay.items():
        H.append(h); V.append(np.frombuffer(v, dtype=np.int8)); K.append(os.path.basename(f)[:-4])
V = np.stack(V).astype(np.float32) / 127.0; V /= np.linalg.norm(V, axis=1, keepdims=True)
idx = {h: i for i, h in enumerate(H)}
print('vektör', len(H), flush=True)
m = g.Model()
def al(u):
    req = urllib.request.Request(u if not u.startswith('//') else 'https:' + u, headers={'User-Agent': g.UA, 'Accept': 'image/*,text/html'})
    with urllib.request.urlopen(req, timeout=25) as r: return r.read()
def onisle(im):
    o = io.BytesIO(); im.convert('RGB').save(o, 'JPEG'); return g.on_isle(o.getvalue())
def boz(im):   # telefon ekran görüntüsü gibi: kırp, küçült, beyaz kenar, düşük kalite
    w, h = im.size; im = im.crop((int(w*.07), int(h*.05), int(w*.93), int(h*.95))).resize((int(w*.8), int(h*.8)))
    im = ImageOps.expand(im, border=(30, 120, 30, 160), fill='white'); o = io.BytesIO(); im.convert('RGB').save(o, 'JPEG', quality=55); return Image.open(io.BytesIO(o.getvalue()))
def ikinci(link):
    try:
        txt = al(link).decode('utf-8', 'replace'); p = yu.jsonld_product(txt); ims = []
        if p:
            im = p.get('image'); ims = im if isinstance(im, list) else [im]
            ims = [x.get('url') if isinstance(x, dict) else x for x in ims]
        ims += re.findall(r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)', txt)
        ims = [x for x in dict.fromkeys(ims) if isinstance(x, str) and x.startswith(('http', '//'))]
        return ims[1] if len(ims) > 1 else None
    except Exception: return None
sonuc = {'ayni': [], 'bozuk': [], 'baska_foto': []}
for o in ornek:
    h = g.hsh(o['l'])
    if h not in idx: print('vektör yok', o['k']); continue
    try: im = Image.open(io.BytesIO(al(o['g'])))
    except Exception as e: print('indirilemedi', o['k']); continue
    tests = [('ayni', im), ('bozuk', boz(im))]
    u2 = ikinci(o['l'])
    if u2:
        try: tests.append(('baska_foto', Image.open(io.BytesIO(al(u2)))))
        except Exception: pass
    for ad, x in tests:
        q = m([onisle(x)])[0].astype(np.float32); q /= np.linalg.norm(q)
        s = V @ q; sira = int((s > s[idx[h]]).sum()) + 1
        sonuc[ad].append(sira)
    print(o['k'], [(a, sonuc[a][-1]) for a, _ in tests], flush=True)
for a, r in sonuc.items():
    r = np.array(r)
    if len(r): print(f'{a}: n={len(r)} ilk1 %{100*np.mean(r<=1):.0f} ilk5 %{100*np.mean(r<=5):.0f} ilk20 %{100*np.mean(r<=20):.0f} ortanca {np.median(r)}')
