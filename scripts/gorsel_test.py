#!/usr/bin/env python3
"""Sitedeki ürün kartlarının görsel adresleri (küçük boy) tarayıcı gibi isteniyor mu: durum, tür, boyut."""
import json, os, re, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def kucuk(u):
    if 'cdn.myikas.com' in u: return u.replace('/1080/', '/360/')
    if re.search(r'/cdn/shop/|cdn\.shopify\.com', u): return u + ('&' if '?' in u else '?') + 'width=360'
    return u
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
iyi = kotu = 0
for o in json.load(open(os.path.join(ROOT, 'data', 'foto_ornek.json'))):
    u = kucuk(o['g']); u = 'https:' + u if u.startswith('//') else u
    for ref in [None, 'https://mubbo1.github.io/']:
        h = {'User-Agent': UA, 'Accept': 'image/avif,image/webp,image/*,*/*'}
        if ref: h['Referer'] = ref
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=20) as r:
                b = r.read(); ok = r.status == 200 and (r.headers.get('Content-Type', '').startswith('image') or b[:4] in (b'RIFF', b'\x89PNG') or b[:2] == b'\xff\xd8')
                print(o['k'], 'ref' if ref else 'yok', r.status, r.headers.get('Content-Type'), len(b), 'OK' if ok else 'KÖTÜ')
        except Exception as e:
            ok = False; print(o['k'], 'ref' if ref else 'yok', 'HATA', str(e)[:80])
        iyi += ok; kotu += not ok
print('toplam iyi', iyi, 'kötü', kotu)
