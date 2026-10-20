#!/usr/bin/env python3
"""Ticimax ürün sayfasının taksit tablosunu (banka listesi) bulur: JS paketlerinde taksit uç noktası arar ve çağırır."""
import json, os, re, sys, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yeni_urun as yu
SITELER = {'Ketench': 'https://ketench.com/erkek-kargo-cepli-gabardin-baggy-pantolon-su-yesilie1001-td544',
           'Ferell Moda': 'https://www.ferellmoda.com/giesto-model-kumas-gomlek-lacivert-20',
           'Semih Kurtulmuş': 'https://semihkurtulmusfashion.com/krem-urban-mont'}
def al(url, acc='*/*', data=None, ct=None):
    h = {'User-Agent': yu.UA, 'Accept': acc, 'Accept-Language': 'tr-TR,tr;q=0.9', 'X-Requested-With': 'XMLHttpRequest'}
    if ct: h['Content-Type'] = ct
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=30) as r:
        return r.read(6_000_000).decode('utf-8', 'replace')
out = {}
for m, u in SITELER.items():
    r = {}; out[m] = r
    try:
        h = al(u, 'text/html'); kok = '{0.scheme}://{0.netloc}'.format(urllib.parse.urlsplit(u))
        r['idler'] = list(dict.fromkeys(re.findall(r'(?:"(?:productId|ProductId|ProductID|urunId|UrunId|UrunID|urunID)"\s*:\s*|(?:productId|urunId|UrunID)\s*=\s*)"?(\d{1,8})', h)))[:10]
        r['urun_kartid'] = list(dict.fromkeys(re.findall(r'"(?:UrunKartiID|urunKartiId|productCardId|ProductCardId)"\s*:\s*(\d+)', h)))[:5]
        js = [urllib.parse.urljoin(u, s) for s in re.findall(r'<script[^>]+src=["\']([^"\']+)', h, re.I)]
        r['js'] = js[:40]; uc = set()
        for s in js[:40]:
            try:
                t = al(s)
            except Exception:
                continue
            for mm in re.finditer(r'(?i)["\'`]([^"\'`\s]{0,80}(?:taksit|installment)[^"\'`\s]{0,80})["\'`]', t):
                uc.add(mm.group(1))
        r['uclar'] = sorted(uc)[:80]
        r['deneme'] = []
        ids = r['idler'][:3] + r['urun_kartid'][:2]
        for path in [p for p in r['uclar'] if p.startswith('/')][:15]:
            for i in ids[:3] or ['']:
                for q in [f'?productId={i}', f'?urunId={i}', f'?productId={i}&price=1000', '']:
                    try:
                        t = al(kok + path + q, 'application/json')
                        r['deneme'].append({'u': path + q, 't': t[:3000]}); break
                    except Exception as e:
                        r['deneme'].append({'u': path + q, 'hata': str(e)[:80]})
                if r['deneme'] and 't' in r['deneme'][-1]: break
        r['html_taksit'] = [h[max(0, x.start() - 300): x.start() + 600] for x in re.finditer(r'(?i)taksit(?:Secenek|Tablo|Table|-table|_table)|installment-?table|bankaLogo|banka-logo', h)][:10]
    except Exception as e:
        r['hata'] = str(e)[:200]
    print(m, r.get('idler'), len(r.get('uclar', [])), flush=True)
json.dump(out, open(os.path.join(yu.DATA, 'banka_ham2.json'), 'w'), ensure_ascii=False, indent=1)
