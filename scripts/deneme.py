import urllib.request, re, sys
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36'
out = []
def get(u):
    r = urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': UA, 'Accept-Language': 'tr-TR'}), timeout=25)
    return r.read().decode('utf-8', 'replace')
sm = get('https://www.erdtrend.com/sitemap.xml')
locs = re.findall(r'<loc>([^<]+)', sm)
out.append(f'LOC {len(locs)} ornek={locs[:15]} son={locs[-10:]}')
for u in ['https://www.erdtrend.com/0-yaka-ithal-ami-15332.aspx', locs[len(locs) // 2]]:
    try:
        t = get(u)
        out.append(f'== {u} len={len(t)}')
        for pat in [r'<meta[^>]+>', r'(?i)<[^>]+(?:price|fiyat)[^>]*>[^<]{0,80}', r'(?i)₺[^<]{0,30}|[0-9.,]+\s*(?:TL|₺)', r'(?i)ld\+json', r'(?i)<h1[^>]*>.{0,200}?</h1>', r'(?i)<img[^>]+(?:urun|product|resim)[^>]+>', r'(?i)stok[^<]{0,60}']:
            out.append(f'  {pat}: {re.findall(pat, t)[:12]}')
    except Exception as e:
        out.append(f'{u} HATA {e}')
open('deneme.txt', 'w').write('\n'.join(out))
