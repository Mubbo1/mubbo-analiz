#!/usr/bin/env python3
"""iade_tara.py'nin net sonuç vermediği siteler için: iade/değişim sayfalarının tam metni (ilk 8000 karakter)."""
import os, re, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yeni_urun as yu
from iade_tara import al, metin

SITELER = {
    'Tudors': ['https://www.tudors.com/iade-sartlari', 'https://www.tudors.com/sikca-sorulan-sorular', 'https://www.tudors.com/'],
    'Ferell Moda': ['https://www.ferellmoda.com/'],
    'Gangown': ['https://gangown.com.tr/'],
    'Bpm Wear': ['https://www.bpmonlinestore.com/'],
    'ErdTrend': ['https://www.erdtrend.com/Sayfalar/iade-sartlari-7.aspx'],
    'Voltaj Giyim': ['https://www.voltaj.com.tr/'],
    'The Champ': ['https://thechamp.com.tr/policies/refund-policy', 'https://thechamp.com.tr/'],
    'VOID TR': ['https://voidtr.com/pages/iade-ve-degisim'],
    'Wunder': ['https://wunder.com.tr/policies/refund-policy', 'https://wunder.com.tr/pages/sss'],
}
ANA = re.compile(r'iade|de[gğ]i[sş]im|refund|return|sss|s[ıi]k', re.I)


def main():
    out = {}
    for marka, urls in SITELER.items():
        sayfalar = []; gor = set()
        kuyruk = list(urls)
        while kuyruk and len(sayfalar) < 5:
            u = kuyruk.pop(0)
            if u in gor:
                continue
            gor.add(u)
            try:
                son, h = al(u)
            except Exception as e:
                sayfalar.append({'url': u, 'metin': 'HATA ' + str(e)[:100]}); continue
            t = metin(h)
            if re.search(r'iade|de[gğ]i[sş]im|cayma', t, re.I) and u not in urls[-1:] or u.endswith(('iade-sartlari', 'refund-policy', 'iade-ve-degisim', '.aspx')):
                i = max(0, t.lower().find('iade') - 300)
                sayfalar.append({'url': son, 'metin': re.sub(r'\n\s*\n+', '\n', t[i:i + 8000])})
            for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', h, re.I | re.S):
                href, yazi = m.group(1), re.sub(r'<[^>]+>', ' ', m.group(2))
                if ANA.search(href) or ANA.search(yazi):
                    v = urllib.parse.urljoin(son, href)
                    if urllib.parse.urlparse(v).netloc == urllib.parse.urlparse(son).netloc and v not in gor:
                        kuyruk.append(v)
        out[marka] = sayfalar
        print(marka, [s['url'] for s in sayfalar], flush=True)
    open(os.path.join(yu.DATA, 'iade_ek.bin'), 'wb').write(yu.sifrele(out))


if __name__ == '__main__':
    main()
