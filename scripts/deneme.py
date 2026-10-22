import sys, json, urllib.request
sys.path.insert(0, 'scripts')
out = []
import yeni_urun as yu
for kok in ['https://www.toriasman.com', 'https://toriasman.com']:
    try:
        req = urllib.request.Request(kok, headers={'User-Agent': yu.UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            h = r.read(600000).decode('utf-8', 'replace'); out.append(f'ANA {kok} -> {r.geturl()} {len(h)}')
        for w in ['ticimax', 'Shopify', 'ikas', 'ideasoft', 'T-Soft', 'tsoft', 'opencart', 'woocommerce', 'myikas', 'faprika', 'shopier']:
            if w.lower() in h.lower(): out.append('  iz: ' + w)
        break
    except Exception as e:
        out.append(f'ANA {kok} HATA {e}')
for path in ['/api/product/GetProductList?PageSize=2', '/products.json?limit=2']:
    try:
        req = urllib.request.Request('https://www.toriasman.com' + path, headers={'User-Agent': yu.UA, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=25) as r: out.append(f'{path} {r.status} {r.read(400)[:300]!r}')
    except Exception as e: out.append(f'{path} HATA {e}')
try:
    s = sorted(yu.sitemap('toriasman.com')); out.append(f'SITEMAP {len(s)}')
    ok = 0
    for u in s[:12]:
        try:
            r = yu.urun_sayfasi(u); ok += bool(r and r.get('fiyat'))
            out.append(f'URUN {u} {json.dumps(r, ensure_ascii=False)[:300]}')
        except Exception as e: out.append(f'URUN {u} HATA {e}')
    out.append(f'FIYATLI {ok}/12')
except Exception as e:
    out.append(f'SITEMAP HATA {e}')
open('deneme.txt', 'w').write('\n'.join(out))
