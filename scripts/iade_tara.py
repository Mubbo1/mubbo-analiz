#!/usr/bin/env python3
"""Rakiplerin iade / değişim koşullarını toplar (tek seferlik araştırma; GitHub Actions'ta çalışır).

Her sitenin ana sayfasındaki bağlantılardan iade, değişim, cayma, teslimat/kargo ve sık sorulan sorular
sayfalarını bulur, sayfa metninden iade ve değişimle ilgili cümleleri çıkarır.
Çıktı: data/iade_ham.bin (şifreli) — {marka: {site, sayfalar: [{url, metin}], hata}}
"""
import concurrent.futures as cf
import html
import os
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yeni_urun as yu

ANAHTAR = re.compile(r'iade|de[gğ]i[sş]im|cayma|return|exchange|kargo|teslimat|s[ıi]k[- ]sorulan|sss|faq|yard[ıi]m|mesafeli', re.I)
CUMLE = re.compile(r'iade|de[gğ]i[sş]|cayma|geri g[öo]nder|kargo [üu]cret|g[üu]n i[çc]inde|hediye [çc]eki|para iadesi|kabul edilme', re.I)


def al(url):
    req = urllib.request.Request(url, headers={'User-Agent': yu.UA, 'Accept': 'text/html', 'Accept-Language': 'tr-TR,tr;q=0.9'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.geturl(), r.read(3_000_000).decode('utf-8', 'replace')


def metin(h):
    h = re.sub(r'(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>', ' ', h)
    h = re.sub(r'(?i)<br\s*/?>|</p>|</li>|</div>|</h\d>', '\n', h)
    t = html.unescape(re.sub(r'<[^>]+>', ' ', h))
    return re.sub(r'[ \t\r\f\v]+', ' ', t)


def ozet(t):
    parcalar = [p.strip() for p in re.split(r'\n+|(?<=[.!?])\s+', t) if p.strip()]
    sec = [p for p in parcalar if CUMLE.search(p) and 15 < len(p) < 600]
    gor = set(); out = []
    for p in sec:
        if p not in gor:
            gor.add(p); out.append(p)
    return '\n'.join(out)[:6000]


def site(marka, host):
    kok = 'https://www.' + host if not host.startswith('www.') else 'https://' + host
    sonuc = {'site': kok, 'sayfalar': [], 'hata': ''}
    try:
        try:
            son, h = al(kok)
        except Exception:
            kok = 'https://' + host; son, h = al(kok)
        sonuc['site'] = son
        linkler = []
        for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', h, re.I | re.S):
            href, yazi = m.group(1), re.sub(r'<[^>]+>', ' ', m.group(2))
            if ANAHTAR.search(href) or ANAHTAR.search(yazi):
                u = urllib.parse.urljoin(son, href)
                if urllib.parse.urlparse(u).netloc.replace('www.', '') == urllib.parse.urlparse(son).netloc.replace('www.', '') and u not in linkler:
                    linkler.append(u)
        # sık kullanılan sayfa adları (bağlantı bulunamazsa)
        for yol in ['/iade-ve-degisim', '/iade-degisim', '/iade-kosullari', '/degisim-ve-iade', '/sayfa/iade-ve-degisim',
                    '/pages/iade-ve-degisim', '/pages/iade-degisim', '/policies/refund-policy', '/sss', '/sikca-sorulan-sorular']:
            u = urllib.parse.urljoin(son, yol)
            if u not in linkler:
                linkler.append(u)
        bulunan = 0
        for u in linkler[:25]:
            try:
                uu, hh = al(u)
            except Exception:
                continue
            oz = ozet(metin(hh))
            if oz and re.search(r'iade|de[gğ]i[sş]im|cayma', oz, re.I):
                sonuc['sayfalar'].append({'url': uu, 'metin': oz})
                bulunan += 1
                if bulunan >= 4:
                    break
    except Exception as e:
        sonuc['hata'] = f'{type(e).__name__}: {str(e)[:150]}'
    print(marka, len(sonuc['sayfalar']), sonuc['hata'], flush=True)
    return marka, sonuc


def main():
    with cf.ThreadPoolExecutor(8) as ex:
        out = dict(ex.map(lambda x: site(*x), yu.RAKIPLER))
    open(os.path.join(yu.DATA, 'iade_ham.bin'), 'wb').write(yu.sifrele(out))


if __name__ == '__main__':
    main()
