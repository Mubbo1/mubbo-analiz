#!/usr/bin/env python3
"""Hangi rakip sitesi ürün sayfasında stok bilgisini veriyor: JSON-LD availability, meta, 'tükendi' yazısı, platform verisi."""
import json, re, sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yeni_urun as yu, katalog as k
random.seed(1)
for key, marka, site, alt in k.MARKALAR:
    if alt != 'harita': continue
    host = site.split('//')[1]
    try: urls = sorted(yu.sitemap(host))
    except Exception as e: print(marka, 'sitemap hata', e); continue
    urls = random.sample(urls, min(25, len(urls)))
    ist = {'ld_var': 0, 'ld_yok_stok': 0, 'meta': 0, 'tukendi_yazi': 0, 'ikas_stok': 0, 'urun': 0, 'stok_false': 0}; ornek = ''
    for u in urls:
        try: txt, _ = yu.get(u, 'text/html')
        except Exception: continue
        p = yu.jsonld_product(txt)
        if not p and not re.search(r'og:type["\'][^>]*product', txt): continue
        ist['urun'] += 1
        if p and re.search(r'availability', json.dumps(p)): ist['ld_var'] += 1
        if p and re.search(r'OutOfStock|SoldOut', json.dumps(p)): ist['ld_yok_stok'] += 1
        if re.search(r'product:availability|og:availability', txt): ist['meta'] += 1
        if re.search(r'(?i)t[üu]kendi|stokta yok|out of stock|sold out', re.sub(r'<script.*?</script>', '', txt, flags=re.S)): ist['tukendi_yazi'] += 1
        m = re.findall(r'"(?:stockCount|stock_count|stockQuantity|quantity|inventory_quantity|totalStock)"\s*:\s*(-?\d+)', txt)
        if m: ist['ikas_stok'] += 1
        if not yu.stok_var(p, txt): ist['stok_false'] += 1
        if not ornek and p: ornek = json.dumps(p.get('offers'), ensure_ascii=False)[:300]
    print(marka, ist, '| offers örnek:', ornek, flush=True)
