import urllib.request, re, socket, sys, json
sys.path.insert(0, 'scripts')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36'
out = []
for h in ['public.trendyol.com', 'apigw.trendyol.com', 'www.trendyol.com', 'erdtrend.com', 'www.erdtrend.com', 'auramoda.com.tr', 'www.auramoda.com.tr', 'bybasicman.com']:
    try:
        out.append(f'DNS {h} {socket.gethostbyname(h)}')
    except Exception as e:
        out.append(f'DNS {h} HATA {e}')
U = ['https://erdtrend.com/', 'https://erdtrend.com/robots.txt', 'https://erdtrend.com/sitemap.xml',
     'https://auramoda.com.tr/', 'https://auramoda.com.tr/robots.txt', 'https://auramoda.com.tr/sitemap.xml',
     'https://erdtrend.com/products.json?limit=2', 'https://auramoda.com.tr/products.json?limit=2',
     'https://apigw.trendyol.com/discovery-web-searchgw-service/v2/api/infinite-scroll/sr?mb=155222&pi=1&culture=tr-TR&userGenderId=1&channelId=1',
     'https://www.trendyol.com/sr?mid=155222', 'https://bybasicman.com/']
for u in U:
    try:
        r = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': UA, 'Accept-Language': 'tr-TR'}), timeout=25)
        t = r.read(400000).decode('utf-8', 'replace')
        gen = re.findall(r'(?i)(ticimax|shopify|ikas|ideasoft|tsoft|woocommerce|wordpress|opencart|myikas|shopier|wix|platinmarket|faprika)', t)[:5]
        out.append(f'{u} {r.status} {r.geturl()} len={len(t)} platform={sorted(set(x.lower() for x in gen))} bas={t[:500]!r}')
    except Exception as e:
        out.append(f'{u} HATA {e}')
try:
    import yeni_urun as yu
    for h in ['erdtrend.com', 'auramoda.com.tr']:
        s = sorted(yu.sitemap(h)); out.append(f'SITEMAP {h} {len(s)} {s[:3]}')
        for u in s[:2]:
            try:
                out.append(f'URUN {u} {json.dumps(yu.urun_sayfasi(u), ensure_ascii=False)[:400]}')
            except Exception as e:
                out.append(f'URUN {u} HATA {e}')
except Exception as e:
    out.append(f'yu HATA {e}')
open('deneme.txt', 'w').write('\n'.join(out))
