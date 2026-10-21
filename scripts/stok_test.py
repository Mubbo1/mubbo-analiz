#!/usr/bin/env python3
"""Kaft ve Tarz Yeri ürün sayfalarında stok bilgisi nerede (yazı/işaret parçaları)."""
import re, sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yeni_urun as yu
random.seed(2)
for host in ['www.kaft.com', 'www.tarzyeri.com', 'erdtrend.com']:
    urls = sorted(yu.sitemap(host)); print('==', host, len(urls), flush=True)
    for u in random.sample(urls, min(4, len(urls))):
        try: txt, _ = yu.get(u, 'text/html')
        except Exception as e: print(u, 'hata', e); continue
        print('--', u, len(txt))
        for m in list(re.finditer(r'(?i)stok|stock|t[üu]kendi|sold.?out|availab|sepete ekle|beden', txt))[:14]:
            print('   ', re.sub(r'\s+', ' ', txt[max(0, m.start() - 120): m.end() + 120]))
