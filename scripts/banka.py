#!/usr/bin/env python3
"""Rakiplerin çalıştığı bankaları ve taksit farklarını toplar (haftalık; GitHub Actions).

- Ticimax siteleri: /api/bank/GetBankInstallments → banka başına taksit tablosu (1.000 TL için toplam tutar).
- PayTR taksit tablosu gömülü siteler: tablo sayfası okunur.
- Diğerleri: ana sayfa, bir ürün sayfası ve ödeme/taksit/sözleşme sayfalarında geçen banka, kart programı,
  ödeme kuruluşu adları ve "x taksit / peşin fiyatına / vade farksız" ifadeleri.
Çıktı: data/banka.bin (şifreli) — [{marka, site, kaynak, bankalar:[{ad, taksit:[[n, toplam_1000]]}], kartlar, kurulus,
        ifadeler, kapida, havale, tarih, hata}]
"""
import concurrent.futures as cf
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yeni_urun as yu

KART = [('Bonus', r'\bbonus'), ('World', r'\bworld(?:card)?\b'), ('Maximum', r'\bmaximum\b'), ('Axess', r'\baxess\b'),
        ('Paraf', r'\bparaf\b'), ('CardFinans', r'card ?finans'), ('Advantage', r'\badvantage\b'), ('Bankkart', r'\bbankkart'),
        ('Saglam Kart', r'sa[gğ]lam ?kart'), ('Miles&Smiles', r'miles ?& ?smiles'), ('Troy', r'\btroy\b')]
BANKA = [('Ziraat Bankası', r'ziraat'), ('Halkbank', r'halk ?bank'), ('VakıfBank', r'vak[ıi]f ?bank'), ('İş Bankası', r'(?:i|İ|ı)[sş] ?bank'),
         ('Garanti BBVA', r'garanti ?bbva|garanti bankas|garantibbva'), ('Akbank', r'\bakbank'), ('Yapı Kredi', r'yap[ıi] ?kredi'), ('QNB', r'\bqnb|finansbank'),
         ('Denizbank', r'deniz ?bank'), ('TEB', r'\bteb\b'), ('ING', r'\bi̇?ng\b|ing bank'), ('HSBC', r'\bhsbc'), ('Kuveyt Türk', r'kuveyt'),
         ('Albaraka', r'albaraka'), ('Türkiye Finans', r't[üu]rkiye finans'), ('Şekerbank', r'[şs]ekerbank'), ('Anadolubank', r'anadolubank'),
         ('Fibabanka', r'fibabanka'), ('Odeabank', r'odeabank'), ('Citibank', r'citibank'), ('Enpara', r'enpara')]
KURULUS = [('iyzico', r'iyzi'), ('PayTR', r'paytr'), ('Param', r'\bparam(?:pos)?\b'), ('Craftgate', r'craftgate'), ('Sipay', r'\bsipay'),
           ('Moka', r'\bmoka'), ('Papara', r'papara'), ('PayPal', r'paypal'), ('Stripe', r'stripe'), ('GarantiPay', r'garanti ?pay'),
           ('Masterpass', r'masterpass'), ('Shopier', r'shopier'), ('ikas Pay', r'ikas ?pay'), ('Shopify Payments', r'shopify ?payments')]
IFADE = re.compile(r'[^.\n]{0,80}(?:\d{1,2} ?(?:aya varan )?taksit|vade fark[ıi]?s[ıi]z|pe[şs]in fiyat[ıi]na|faizsiz)[^.\n]{0,80}', re.I)
LINK = re.compile(r'taksit|odeme|ödeme|payment|banka|hesap|havale|mesafeli|guvenli|güvenli|sss|yardim|yardım', re.I)


def al(url, acc='text/html'):
    req = urllib.request.Request(url, headers={'User-Agent': yu.UA, 'Accept': acc, 'Accept-Language': 'tr-TR,tr;q=0.9', 'X-Requested-With': 'XMLHttpRequest'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.geturl(), r.read(4_000_000).decode('utf-8', 'replace')


def metin(h):
    ek = ' '.join(re.findall(r'(?:alt|title)=["\']([^"\']{2,60})["\']', h, re.I)) + ' ' + \
         ' '.join(os.path.basename(urllib.parse.urlsplit(s).path) for s in re.findall(r'<img[^>]+(?:data-)?src=["\']([^"\']+)', h, re.I))
    h = re.sub(r'(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>', ' ', h)
    h = re.sub(r'(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>|</tr>|</td>', '\n', h)
    return re.sub(r'[ \t\r\f\v]+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h))), ek


def ad_bul(liste, t):
    return [a for a, rx in liste if re.search(rx, t, re.I)]


def ticimax(kok):
    try:
        _, t = al(kok + '/api/bank/GetBankInstallments?Amount=1000&MaxInstallment=12&CurrencyCode=TRY', 'application/json')
        j = json.loads(t)
    except Exception:
        return None
    if not isinstance(j, dict) or 'bankInstallments' not in j:
        return None
    out = []
    for b in j.get('bankInstallments') or []:
        ins = next((v for v in b.values() if isinstance(v, list)), [])
        out.append({'ad': (b.get('bankName') or '').strip(), 'taksit': [[i.get('installment'), round(i.get('totalAmount') or 0, 2)] for i in ins if i.get('installment')]})
    return out


def paytr(h):
    m = re.search(r'https://www\.paytr\.com/odeme/taksit-tablosu/v2\?[^"\'<>\s]+', h)
    if not m:
        return None
    u = html.unescape(m.group(0))
    if 'amount=' not in u:
        u += '&amount=1000'
    try:
        _, t = al(u)
    except Exception:
        return None
    tx, _ = metin(t)
    return {'url': u, 'kartlar': ad_bul(KART, tx), 'metin': tx[:4000]}


def tek(marka, host):
    kok = 'https://' + (host if host.startswith('www.') else 'www.' + host)
    r = {'marka': marka, 'site': host, 'kaynak': '', 'bankalar': [], 'kartlar': [], 'kurulus': [], 'ifadeler': [], 'kapida': False, 'havale': False, 'hata': ''}
    try:
        try:
            son, h = al(kok)
        except Exception:
            kok = 'https://' + host; son, h = al(kok)
        kok = '{0.scheme}://{0.netloc}'.format(urllib.parse.urlsplit(son))
        tic = ticimax(kok)
        if tic:
            r['bankalar'] = tic; r['kaynak'] = 'Sitenin taksit tablosu'
        sayfalar = [h]
        linkler = []
        for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', h, re.I | re.S):
            href, yazi = m.group(1), re.sub(r'<[^>]+>', ' ', m.group(2))
            if LINK.search(href) or LINK.search(yazi):
                u = urllib.parse.urljoin(son, href)
                if urllib.parse.urlsplit(u).netloc == urllib.parse.urlsplit(son).netloc and u not in linkler:
                    linkler.append(u)
        try:   # bir ürün sayfası (taksit tablosu çoğu zaman orada)
            for u in sorted(yu.sitemap(host))[:40]:
                if yu.urun_sayfasi(u):
                    linkler.insert(0, u); break
        except Exception:
            pass
        for u in linkler[:14]:
            try:
                sayfalar.append(al(u)[1])
            except Exception:
                pass
        tum = ''; ekler = ''
        for s in sayfalar:
            tx, ek = metin(s); tum += '\n' + tx; ekler += ' ' + ek
            if not r['bankalar']:
                p = paytr(s)
                if p:
                    r['paytr'] = p; r['kaynak'] = 'PayTR taksit tablosu'
        ham = '\n'.join(sayfalar)
        # banka / kart adları yalnız görsel adlarında ya da taksit-kart-banka sözcüklerinin yakınında aranır (yanlış eşleşmeyi önler)
        yakin = ' '.join(tum[max(0, m.start() - 150): m.end() + 150] for m in re.finditer(r'taksit|kredi kart|banka|ödeme se[çc]enek|odeme', tum, re.I))
        baglam = ekler + ' ' + yakin + ' ' + (r.get('paytr') or {}).get('metin', '')
        r['kartlar'] = ad_bul(KART, baglam)
        if not r['bankalar']:
            r['banka_adlari'] = ad_bul(BANKA, baglam)
        r['kurulus'] = ad_bul(KURULUS, tum + ' ' + ekler + ' ' + ' '.join(re.findall(r'src=["\']([^"\']+)', ham)))
        ifa = []
        for x in IFADE.findall(tum):
            x = ' '.join(x.split()).strip(' -•|')
            if len(x) > 140:   # kayan yazı tekrarları: ifadenin geçtiği kısa parça
                m = re.search(r'.{0,50}(?:\d{1,2} ?taksit|vade fark[ıi]?s[ıi]z|pe[şs]in fiyat[ıi]na|faizsiz).{0,40}', x, re.I)
                x = m.group(0).strip(' -•|') if m else x[:140]
            if not any(x.lower() in y.lower() or y.lower() in x.lower() for y in ifa):
                ifa.append(x)
        r['ifadeler'] = ifa[:6]
        r['kapida'] = bool(re.search(r'kap[ıi]da [öo]deme', tum, re.I))
        r['havale'] = bool(re.search(r'havale|\beft\b', tum, re.I))
        if not r['kaynak']:
            r['kaynak'] = 'Site metni' if (r['kartlar'] or r.get('banka_adlari') or r['ifadeler'] or r['kurulus']) else 'Bilgi bulunamadı'
        r.pop('paytr', None) if not r.get('paytr') else r['paytr'].pop('metin', None)
    except Exception as e:
        r['hata'] = f'{type(e).__name__}: {e}'[:160]; r['kaynak'] = 'Site açılmadı'
    print(marka, r['kaynak'], len(r['bankalar']), r['kartlar'], r['kurulus'], r['hata'], flush=True)
    return r


def main():
    with cf.ThreadPoolExecutor(8) as ex:
        out = list(ex.map(lambda x: tek(*x), yu.RAKIPLER))
    tarih = (dt.datetime.utcnow() + dt.timedelta(hours=3)).strftime('%Y-%m-%d')
    for r in out:
        r['tarih'] = tarih
    open(os.path.join(yu.DATA, 'banka.bin'), 'wb').write(yu.sifrele(out))


if __name__ == '__main__':
    main()
