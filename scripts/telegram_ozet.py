#!/usr/bin/env python3
"""Her sabah rakip özetini Telegram'a gönderir (Claude kullanmaz, GitHub'da ücretsiz çalışır).

Veri: data/degisim.bin (gecmis.py her gün katalogla birlikte üretir).
Gereken depo sırları: MUBBO_SIFRE, TG_BOT_TOKEN (BotFather'dan alınan anahtar). TG_CHAT_ID isteğe bağlı: yoksa bota en son yazan sohbete gider.
TG_BOT_TOKEN yoksa hiçbir şey göndermeden çıkar.
Kullanım: python3 scripts/telegram_ozet.py [--dene]   (--dene: göndermez, mesajı ekrana yazar)
"""
import html, json, os, sys, urllib.parse, urllib.request
import datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_eslestir as t

DATA = t.DATA
SITE = 'https://mubbo1.github.io/mubbo-analiz/'
AY = ['', 'Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']


def tl(v):
    return f'{v:,.0f}'.replace(',', '.') + ' ₺' if v is not None else '—'


def gun(s):
    d = dt.date.fromisoformat(s); return f'{d.day} {AY[d.month]}'


def kisa(s, n=48):
    s = ' '.join((s or '').split()); return s if len(s) <= n else s[:n - 1] + '…'


def e(s):
    return html.escape(str(s), quote=False)


def mesaj():
    o = t.ozel_anahtar(); d = t.coz(os.path.join(DATA, 'degisim.bin'), o)
    son = (d.get('gunluk') or [{}])[-1]
    s = [f'<b>MUBBO · Rakiplerde {gun(d["tarih"])}</b>', '']
    s.append(f'🟢 {son.get("dus", 0)} ürün indirime girdi')
    s.append(f'🔴 {son.get("art", 0)} ürün zamlandı')
    s.append(f'🟣 {son.get("bitti", 0)} ürün stoktan çıktı')
    s.append(f'🟡 {len(d.get("hizli", []))} ürün tükenmek üzere')
    dus = [x for x in d.get('dus', []) if x.get('tarih') == d['tarih']][:5]
    if dus:
        s += ['', '<b>Dünün en büyük indirimleri</b>']
        s += [f'• {e(x["m"])} · <a href="{e(x["l"])}">{e(kisa(x["u"]))}</a> {tl(x["onceki"])} → {tl(x["yeni"])} ({x["yuzde"]:+.0f}%)' for x in dus]
    hz = d.get('hizli', [])[:5]
    if hz:
        s += ['', '<b>Çok satıp tükenmek üzere</b>']
        s += [f'• {e(x["m"])} · <a href="{e(x["l"])}">{e(kisa(x["u"]))}</a> — {x["stok"]:.0f} adet kaldı, günde ~{x["gunluk"]:.0f}' for x in hz]
    ym = sorted((d.get('yeni_marka') or {}).items(), key=lambda x: -x[1])[:5]
    if son.get('yeni') or ym:
        s += ['', f'<b>{son.get("yeni", 0)} yeni ürün eklendi</b>']
        if ym:
            s.append('Son 7 günde en çok ekleyen: ' + ', '.join(f'{e(m)} {n}' for m, n in ym))
    s += ['', f'<a href="{SITE}">Siteyi aç →</a>']
    return '\n'.join(s)


def main():
    m = mesaj()
    if '--dene' in sys.argv:
        print(m); return
    tok, chat = os.environ.get('TG_BOT_TOKEN'), os.environ.get('TG_CHAT_ID')
    if not tok:
        print('TG_BOT_TOKEN sırrı tanımlı değil; mesaj gönderilmedi.'); return
    yol = os.path.join(DATA, 'tg_sohbet.bin'); o = t.ozel_anahtar()
    if not chat:   # sohbet numarası: önce kayıtlı (şifreli) dosyadan, yoksa bota en son yazan kişiden
        up = json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/getUpdates', timeout=30)).get('result', [])
        ids = [(u.get('message') or u.get('my_chat_member') or {}).get('chat', {}).get('id') for u in up]
        ids = [i for i in ids if i]
        if ids:
            chat = ids[-1]
            try:
                eski = t.coz(yol, o).get('chat') if os.path.exists(yol) else None
            except Exception:
                eski = None
            if eski != chat:
                open(yol, 'wb').write(t.sifrele({'chat': chat}, o))
        elif os.path.exists(yol):
            chat = t.coz(yol, o).get('chat')
        if not chat:
            print('Bota henüz kimse yazmadı: Telegram\'da bota /start yazın.'); return
    veri = urllib.parse.urlencode({'chat_id': chat, 'text': m, 'parse_mode': 'HTML', 'disable_web_page_preview': 'true'}).encode()
    r = json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage', veri, timeout=30))
    print('gönderildi' if r.get('ok') else r)


if __name__ == '__main__':
    main()
