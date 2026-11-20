#!/usr/bin/env python3
"""Takip listesi + Telegram uyarısı (Claude kullanmaz, GitHub'da ücretsiz çalışır).

Bot (TG_BOT_TOKEN) üzerinden:
- Siteden "Telegram'da takip et" düğmesi botu /start t_<kod> ile açar -> ürün takibe alınır.
- Bota bir rakip ürün linki yazılırsa o ürün takibe alınır.
- /liste: takip edilenler · /sil <numara>: listeden çıkarır.
Her çalışmada (katalog yenilenince) takip edilen ürünlerin fiyatı kontrol edilir; fiyat değiştiyse ya da ürün stoktan
çıktıysa bota mesaj gelir. Liste data/tg_takip.bin dosyasında şifreli tutulur; site de aynı listeyi gösterir.
Kullanım: python3 scripts/tg_takip.py [--kontrol]   (--kontrol: fiyat/stok uyarılarını da gönder)
"""
import hashlib, html, json, os, re, sys, urllib.parse, urllib.request
import datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_eslestir as t

DATA = t.DATA
YOL = os.path.join(DATA, 'tg_takip.bin')
SITE = 'https://mubbo1.github.io/mubbo-analiz/'


def kod(l):
    return hashlib.sha1(l.encode()).hexdigest()[:12]


def tl(v):
    return f'{v:,.0f}'.replace(',', '.') + ' ₺' if v is not None else '—'


def e(s):
    return html.escape(str(s), quote=False)


def api(tok, yontem, **p):
    veri = urllib.parse.urlencode(p).encode() if p else None
    return json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/{yontem}', veri, timeout=40))


def yaz(tok, chat, metin):
    try:
        api(tok, 'sendMessage', chat_id=chat, text=metin, parse_mode='HTML', disable_web_page_preview='true')
    except Exception as ex:
        print('gönderilemedi:', ex)


def katalog(o):
    d = t.coz(os.path.join(DATA, 'katalog_site.bin'), o)
    rows = d.get('rows', d) if isinstance(d, dict) else d
    return {r['l']: r for r in rows if r.get('l')}


def main():
    tok = os.environ.get('TG_BOT_TOKEN')
    if not tok:
        print('TG_BOT_TOKEN yok'); return
    o = t.ozel_anahtar()
    try:
        S = t.coz(YOL, o)
    except Exception:
        S = {'offset': 0, 'liste': [], 'chat': None}
    try:
        S['chat'] = S.get('chat') or t.coz(os.path.join(DATA, 'tg_sohbet.bin'), o).get('chat')
    except Exception:
        pass
    K = katalog(o); kodlar = {kod(l): l for l in K}
    norm = {}
    for l in K:
        p = urllib.parse.urlsplit(l); norm[(p.netloc.lower().removeprefix('www.') + p.path.rstrip('/').lower())] = l
    degisti = False

    def ekle(chat, l):
        nonlocal degisti
        r = K[l]
        if any(x['l'] == l for x in S['liste']):
            yaz(tok, chat, f'Bu ürün zaten takipte: <b>{e(r["m"])}</b> · {e(r["u"])}'); return
        S['liste'].append({'l': l, 'm': r['m'], 'u': r['u'], 'g': r.get('g'), 'f0': r['f'], 'fs': r['f'], 't': dt.date.today().isoformat(), 'yok': False})
        degisti = True
        yaz(tok, chat, f'⭐ Takibe alındı: <b>{e(r["m"])}</b> · <a href="{e(l)}">{e(r["u"])}</a> — {tl(r["f"])}\n'
                       f'Fiyatı değişirse ya da stoktan çıkarsa sana yazacağım. Listeyi görmek için /liste')

    # 1) bota gelen mesajlar
    try:
        up = api(tok, 'getUpdates', offset=S.get('offset', 0) + 1 if S.get('offset') else 0, timeout=0).get('result', [])
    except Exception as ex:
        print('mesajlar okunamadı:', ex); up = []
    for u in up:
        S['offset'] = max(S.get('offset', 0), u['update_id']); degisti = True
        m = u.get('message') or {}; chat = (m.get('chat') or {}).get('id'); metin = (m.get('text') or '').strip()
        if not chat or not metin:
            continue
        S['chat'] = chat
        k = re.match(r'/start\s+t_([0-9a-f]{12})', metin)
        if k:
            l = kodlar.get(k.group(1))
            yaz(tok, chat, 'Bu ürün artık rakibin sitesinde stokta görünmüyor.') if not l else ekle(chat, l)
            continue
        if metin.startswith('/liste'):
            if not S['liste']:
                yaz(tok, chat, 'Takip listen boş. Sitede bir ürüne dokunup "Telegram\'da takip et"e bas ya da bana ürün linkini gönder.')
            else:
                s = ['<b>⭐ Takip listen</b>']
                for i, x in enumerate(S['liste'], 1):
                    r = K.get(x['l']); f = r['f'] if r else None
                    durum = 'stokta yok' if not r else (f'{tl(x["f0"])} → <b>{tl(f)}</b>' if abs(f - x['f0']) >= 1 else tl(f))
                    s.append(f'{i}. <b>{e(x["m"])}</b> · <a href="{e(x["l"])}">{e(x["u"][:50])}</a> — {durum}')
                s.append('\nÇıkarmak için: /sil numara (ör. /sil 2)')
                yaz(tok, chat, '\n'.join(s))
            continue
        k = re.match(r'/sil\s+(\d+)', metin)
        if k:
            i = int(k.group(1)) - 1
            if 0 <= i < len(S['liste']):
                x = S['liste'].pop(i); degisti = True; yaz(tok, chat, f'Takipten çıkarıldı: {e(x["u"])}')
            else:
                yaz(tok, chat, 'Bu numarada ürün yok. /liste yazıp numaraya bak.')
            continue
        # Kâr analizi: siteden kopyalanan "fiyat <ürün kodu> <toptan fiyat>" satırları ve "alarm <kâr yüzdesi>"
        fy = re.findall(r'(?im)^\s*fiyat\s+([A-Za-z0-9_.-]+)\s+(\d+(?:[.,]\d+)?)\s*$', metin)
        al = re.search(r'(?im)^\s*alarm\s+%?(\d{1,3})\s*$', metin)
        if fy or al:
            S.setdefault('fiyat', {})
            for kod_, v in fy:
                S['fiyat'][kod_] = float(v.replace(',', '.'))
            if al:
                S['alarm'] = int(al.group(1))
            degisti = True
            yaz(tok, chat, f'💾 Kaydedildi: {len(fy)} toptan fiyat' + (f', kâr alarmı %{S["alarm"]}' if al else '') + '. Sitedeki Kâr Analizi her cihazda bu fiyatları gösterecek.')
            continue
        linkler = re.findall(r'https?://\S+', metin)
        if linkler:
            for l0 in linkler:
                p = urllib.parse.urlsplit(l0); n = p.netloc.lower().removeprefix('www.') + urllib.parse.unquote(p.path).rstrip('/').lower()
                l = norm.get(n) or K.get(l0)
                yaz(tok, chat, 'Bu linki rakip kataloglarında bulamadım (rakip sitesindeki ürün sayfasının linki olmalı).') if not l else ekle(chat, l)
            continue
        if metin.startswith('/start'):
            yaz(tok, chat, 'Merhaba! Her sabah 09.00\'da rakip raporunu buraya gönderiyorum.\n\n'
                           '⭐ <b>Ürün takibi:</b> Sitede bir ürüne dokunup "Telegram\'da takip et"e bas ya da bana rakip ürün linkini gönder. '
                           'Fiyatı değişince ya da stoktan çıkınca haber veririm.\n/liste — takip ettiklerin')
            continue
        yaz(tok, chat, 'Ürün takibi için rakip ürün linkini gönder. Takip listen için /liste yaz.')

    # 2) fiyat / stok kontrolü
    if '--kontrol' in sys.argv and S['liste'] and S.get('chat'):
        uyari = []
        for x in S['liste']:
            r = K.get(x['l'])
            if not r:
                if not x.get('yok'):
                    x['yok'] = True; degisti = True
                    uyari.append(f'🟣 <b>{e(x["m"])}</b> · <a href="{e(x["l"])}">{e(x["u"][:55])}</a>\n   stoktan çıktı (son fiyat {tl(x["fs"])})')
                continue
            if x.get('yok'):
                x['yok'] = False; degisti = True
                uyari.append(f'🔵 <b>{e(x["m"])}</b> · <a href="{e(x["l"])}">{e(x["u"][:55])}</a>\n   yeniden stokta: {tl(r["f"])}')
            if r['f'] and x.get('fs') and abs(r['f'] - x['fs']) >= 1:
                yz = round(100 * (r['f'] - x['fs']) / x['fs'])
                uyari.append(f'{"🟢" if yz < 0 else "🔴"} <b>{e(x["m"])}</b> · <a href="{e(x["l"])}">{e(x["u"][:55])}</a>\n'
                             f'   {tl(x["fs"])} → <b>{tl(r["f"])}</b> ({yz:+d}%)')
                x['fs'] = r['f']; degisti = True
        if uyari:
            yaz(tok, S['chat'], '<b>⭐ Takip listende değişiklik</b>\n\n' + '\n'.join(uyari) + f'\n\n<a href="{SITE}">Siteyi aç →</a>')
        print(len(uyari), 'uyarı')
    if degisti or not os.path.exists(YOL):
        open(YOL, 'wb').write(t.sifrele(S, o))
    print(len(S['liste']), 'ürün takipte;', len(up), 'mesaj işlendi')


if __name__ == '__main__':
    main()
