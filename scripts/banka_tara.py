#!/usr/bin/env python3
"""Rakiplerin çalıştığı bankaları / ödeme kuruluşlarını araştırır (tek seferlik; GitHub Actions'ta çalışır).

Ana sayfa, ürün sayfası, ödeme / banka hesapları / taksit / sözleşme sayfalarındaki banka, kart programı ve
ödeme kuruluşu adlarını bağlamlarıyla toplar. Çıktı: data/banka_ham.json (herkese açık site bilgisi).
"""
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yeni_urun as yu

SITELER = {
    'Ketench': ('https://ketench.com', 'https://ketench.com/erkek-kargo-cepli-gabardin-baggy-pantolon-su-yesilie1001-td544'),
    'Ferell Moda': ('https://www.ferellmoda.com', 'https://www.ferellmoda.com/giesto-model-kumas-gomlek-lacivert-20'),
    'Semih Kurtulmuş': ('https://semihkurtulmusfashion.com', 'https://semihkurtulmusfashion.com/krem-urban-mont'),
}
BANKA = re.compile(r'ziraat|halkbank|halk bankas|vak[ıi]f|i[sş] bankas|i[sş]bank|garanti|akbank|yap[ıi] ?kredi|qnb|finansbank|denizbank|teb\b|'
                   r'ing\b|hsbc|kuveyt|albaraka|t[üu]rkiye finans|enpara|odea|fibabanka|[şs]ekerbank|anadolubank|alternatif|burgan|icbc|'
                   r'bonus|world\b|worldcard|maximum|axess|paraf|cardfinans|card finans|advantage|bankkart|saglam kart|sa[gğ]lam kart|miles ?& ?smiles|'
                   r'iyzico|iyzi|paytr|param\b|craftgate|sipay|moka|ödeal|papara|tosla|stripe|paypal|masterpass|troy|visa|mastercard|amex|'
                   r'havale|eft|iban|tr\d{2}[ \d]{10,}|taksit|sanal pos|vpos|kap[ıi]da [öo]deme', re.I)
LINK = re.compile(r'banka|hesap|havale|eft|taksit|odeme|ödeme|payment|mesafeli|sozlesme|sözleşme|guvenli|güvenli|kvkk|gizlilik|yardim|yardım|sss|iletisim|iletişim', re.I)


def al(url, accept='text/html'):
    req = urllib.request.Request(url, headers={'User-Agent': yu.UA, 'Accept': accept, 'Accept-Language': 'tr-TR,tr;q=0.9'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.geturl(), r.read(4_000_000).decode('utf-8', 'replace')


def metin(h):
    alts = ' '.join(re.findall(r'(?:alt|title)=["\']([^"\']{2,60})["\']', h, re.I))
    srcs = ' '.join(os.path.basename(urllib.parse.urlsplit(s).path) for s in re.findall(r'<img[^>]+src=["\']([^"\']+)', h, re.I))
    h = re.sub(r'(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>', ' ', h)
    h = re.sub(r'(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>|</tr>|</td>', '\n', h)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', h))
    return re.sub(r'[ \t\r\f\v]+', ' ', t) + '\nGÖRSEL-ALT: ' + alts + '\nGÖRSEL-DOSYA: ' + srcs


def bul(t):
    out = []
    for p in re.split(r'\n+', t):
        p = p.strip()
        if BANKA.search(p) and len(p) < 700:
            out.append(p[:700])
    return list(dict.fromkeys(out))[:60]


def main():
    sonuc = {}
    for marka, (kok, urun) in SITELER.items():
        r = {'sayfalar': []}
        try:
            son, h = al(kok)
            linkler = [urun]
            for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', h, re.I | re.S):
                href, yazi = m.group(1), re.sub(r'<[^>]+>', ' ', m.group(2))
                if LINK.search(href) or LINK.search(yazi):
                    u = urllib.parse.urljoin(son, href)
                    if urllib.parse.urlsplit(u).netloc == urllib.parse.urlsplit(son).netloc and u not in linkler:
                        linkler.append(u)
            for yol in ['/banka-hesaplari', '/banka-hesap-bilgileri', '/hesap-numaralarimiz', '/havale-bilgileri', '/odeme-secenekleri',
                        '/taksit-secenekleri', '/mesafeli-satis-sozlesmesi', '/guvenli-alisveris']:
                u = urllib.parse.urljoin(son, yol)
                if u not in linkler:
                    linkler.append(u)
            r['sayfalar'].append({'url': son, 'bulgu': bul(metin(h))})
            api = set(re.findall(r'["\'](/api/[A-Za-z/]*(?:[Ii]nstallment|[Tt]aksit|[Bb]ank|[Pp]ayment)[A-Za-z/]*)', h))
            for u in linkler[:30]:
                try:
                    uu, hh = al(u)
                except Exception as e:
                    continue
                api |= set(re.findall(r'["\'](/api/[A-Za-z/]*(?:[Ii]nstallment|[Tt]aksit|[Bb]ank|[Pp]ayment)[A-Za-z/]*)', hh))
                b = bul(metin(hh))
                if b:
                    r['sayfalar'].append({'url': uu, 'bulgu': b})
                if u == urun:
                    r['ham'] = [hh[max(0, m.start() - 200): m.start() + 300] for m in re.finditer(r'aksit|nstallment|BankaLogo|bankalogo|iyzi|paytr|Odeme|payment', hh)][:40]
                    r['uclar'] = sorted(set(re.findall(r'["\'](/(?:api|Urun|urun|Product|Taksit|Sepet)[A-Za-z/_.-]*)', hh)))[:200]
                    pid = re.search(r'(?:productId|ProductId|urunId|UrunID)["\']?\s*[:=]\s*["\']?(\d+)', hh)
                    r['urun_id'] = pid.group(1) if pid else None
            r['api'] = sorted(api)
            for a in sorted(api)[:10]:
                for q in ([f'?productId={r.get("urun_id")}', f'?ProductId={r.get("urun_id")}&price=1000'] if r.get('urun_id') else ['']):
                    try:
                        uu, hh = al(urllib.parse.urljoin(son, a + q), 'application/json')
                        r['sayfalar'].append({'url': uu, 'bulgu': bul(hh) or [hh[:1500]]})
                    except Exception as e:
                        r['sayfalar'].append({'url': a + q, 'hata': str(e)[:100]})
        except Exception as e:
            r['hata'] = f'{type(e).__name__}: {e}'[:200]
        print(marka, len(r['sayfalar']), r.get('api'), r.get('hata', ''), flush=True)
        sonuc[marka] = r
    json.dump(sonuc, open(os.path.join(yu.DATA, 'banka_ham.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
