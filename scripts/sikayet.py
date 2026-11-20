#!/usr/bin/env python3
"""Rakiplerin Şikayetvar sayfalarını okur (Claude kullanmaz, GitHub'da ücretsiz çalışır).

Her rakip için: Şikayetvar puanı (/100), değerlendirme sayısı, toplam şikâyet sayısı, son şikâyetlerin başlığı/tarihi,
konu dağılımı (kargo, iade, beden, kalite...). Sayfa adresi bir kez aramayla bulunur ve data/sikayet_sayfalar.json'da saklanır.
Çıktı: data/sikayet_durum.bin (şifreli) — {tarih, markalar: [...], gecmis: {marka: [[gün, şikâyet sayısı], ...]}}
"""
import gzip, html, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
import datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_eslestir as t
import yeni_urun as yu

DATA = t.DATA
SV = 'https://www.sikayetvar.com'
SAYFA = os.path.join(DATA, 'sikayet_sayfalar.json')
CIKTI = os.path.join(DATA, 'sikayet_durum.bin')
KALDIR = {'Tudors', 'Tommylife', 'Aura Moda'}
AY = {'ocak': 1, 'şubat': 2, 'mart': 3, 'nisan': 4, 'mayıs': 5, 'haziran': 6, 'temmuz': 7, 'ağustos': 8, 'eylül': 9, 'ekim': 10, 'kasım': 11, 'aralık': 12}
KONU = [('Kargo / teslimat', r'kargo|teslim|gelmedi|ulaşmadı|gecik|sipariş.*(gelmedi|ulaşmadı)'),
        ('İade / para iadesi', r'iade|para.*(geri|iade)|ücret.*kes|değişim'),
        ('Beden / kalıp', r'beden|kalıp|küçük|büyük|dar\b|bol\b'),
        ('Kalite / kusur', r'kalite|yırt|sök|defo|kusur|bozuk|solma|boya|tüylen|çekme|leke|koku'),
        ('Yanlış / eksik ürün', r'yanlış|eksik|farklı ürün|farklılık|vaat'),
        ('Ödeme', r'ödeme|kart|çekildi|para'),
        ('Müşteri hizmetleri', r'ulaşam|cevap|yanıt|muhatap|iletişim|müşteri hizmet')]


def fold(s):
    s = (s or '').replace('İ', 'i').replace('I', 'ı').lower().translate(str.maketrans('çğıöşü', 'cgiosu'))
    return re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKD', s))


def get(u):
    req = urllib.request.Request(u, headers={'User-Agent': yu.UA, 'Accept': 'text/html,*/*', 'Accept-Language': 'tr-TR,tr;q=0.9'})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                b = r.read()
                return (gzip.decompress(b) if b[:2] == b'\x1f\x8b' else b).decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            if e.code == 404 or i == 2:
                raise
        except Exception:
            if i == 2:
                raise
        time.sleep(4 * (i + 1))


def bul(marka, alan):
    """Arama sonucundaki ilk şirket sayfası; adı markayla uyuşmalı"""
    h = get(SV + '/arama?k=' + urllib.parse.quote(marka))
    ana = fold(marka.split()[0]) if len(fold(marka.split()[0])) >= 4 else fold(marka)
    alan_f = fold(alan.split('.')[0])
    for yol, ad in re.findall(r'href="(/[a-z0-9-]+)"[^>]*>([^<]{2,60})</a>', h):
        if yol in ('/canli-yayin', '/sikayetler', '/trend-100', '/tv', '/arama', '/hakkimizda'):
            continue
        f = fold(html.unescape(ad))
        if f and (ana in f or f in alan_f or alan_f in fold(yol)):
            return yol
    return None


def tarih(s, bugun):
    m = re.match(r'(\d{1,2}) ([A-Za-zÇĞİÖŞÜçğıöşü]+)(?: (\d{4}))?', s.strip())
    if not m:
        return None
    ay = AY.get(m.group(2).lower().replace('I', 'ı'))
    if not ay:
        return None
    yil = int(m.group(3)) if m.group(3) else (bugun.year if (ay, int(m.group(1))) <= (bugun.month, bugun.day) else bugun.year - 1)
    try:
        return dt.date(yil, ay, int(m.group(1))).isoformat()
    except ValueError:
        return None


def oku(yol, bugun):
    h = get(SV + yol)
    puan = re.search(r'>(\d{1,3})</span><span[^>]*>/100</span>', h)
    deg = re.search(r'(\d[\d.]*) değerlendirme', h)
    say = re.search(r'>([\d.]+) şikayet<', h)
    kartlar = []
    for b in h.split('data-inp="Complaint_Card_Title"')[1:]:
        bas = re.search(r'href="([^"]+)">([^<]+)</a>', b)
        tr = re.search(r'data-inp="Date_Tooltip">([^<]+)<', b)
        if bas:
            kartlar.append({'b': html.unescape(bas.group(2)).strip(), 'l': SV + bas.group(1), 't': tarih(tr.group(1), bugun) if tr else None})
    return {'puan': int(puan.group(1)) if puan else None, 'degerlendirme': int(deg.group(1).replace('.', '')) if deg else 0,
            'sikayet': int(say.group(1).replace('.', '')) if say else len(kartlar), 'son': kartlar[:10]}


def main():
    o = t.ozel_anahtar(); bugun = (dt.datetime.utcnow() + dt.timedelta(hours=3)).date()
    sayfa = json.load(open(SAYFA)) if os.path.exists(SAYFA) else {}
    try:
        eski = t.coz(CIKTI, o)
    except Exception:
        eski = {'gecmis': {}}
    gec = eski.get('gecmis', {}); out = []
    for marka, alan in yu.RAKIPLER:
        if marka in KALDIR:
            continue
        try:
            if marka not in sayfa:
                sayfa[marka] = bul(marka, alan); time.sleep(1)
            yol = sayfa[marka]
            if not yol:
                out.append({'marka': marka, 'yok': True}); continue
            d = oku(yol, bugun); d.update(marka=marka, sayfa=SV + yol)
            sinir = (bugun - dt.timedelta(days=90)).isoformat()
            son90 = [k for k in d['son'] if k['t'] and k['t'] >= sinir]
            konu = {}
            for k in d['son']:
                for ad, rx in KONU:
                    if re.search(rx, k['b'].lower()):
                        konu[ad] = konu.get(ad, 0) + 1; break
            d['konu'] = konu; d['son90'] = len(son90)
            g = gec.setdefault(marka, [])
            if not g or g[-1][0] != bugun.isoformat():
                g.append([bugun.isoformat(), d['sikayet']])
            gec[marka] = g[-120:]
            out.append(d); print(marka, yol, d['puan'], d['sikayet'], flush=True)
        except Exception as ex:
            print('HATA', marka, ex, flush=True)
            out.append({'marka': marka, 'hata': str(ex)[:80]})
        time.sleep(1.5)
    json.dump(sayfa, open(SAYFA, 'w'), ensure_ascii=False, indent=1)
    open(CIKTI, 'wb').write(t.sifrele({'tarih': bugun.isoformat(), 'markalar': out, 'gecmis': gec}, o))
    print(sum(1 for x in out if x.get('sikayet') is not None), 'marka okundu')


if __name__ == '__main__':
    main()
