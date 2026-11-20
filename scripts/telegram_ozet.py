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
from artifact_tel import aksesuar

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
    """Ayrıntılı günlük rapor; Telegram'ın 4096 karakter sınırı için birkaç mesaja bölünür."""
    o = t.ozel_anahtar(); d = t.coz(os.path.join(DATA, 'degisim.bin'), o)
    gl = d.get('gunluk') or [{}]; son = gl[-1]; gun_ = d['tarih']
    once = [g for g in gl[:-1]][-7:]
    ort = lambda k: (sum(g.get(k, 0) for g in once) / len(once)) if once else 0
    sup = set(d.get('supheli') or [])
    def kiyas(k):
        a = ort(k); v = son.get(k, 0)
        if not a: return ''
        f = round(100 * (v - a) / a)
        return f' <i>(7 gün ort. {a:.0f}, {"+" if f >= 0 else ""}{f}%)</i>' if abs(f) >= 15 else f' <i>(ort. {a:.0f})</i>'
    bl = []
    # 1) genel tablo
    s = [f'<b>📊 MUBBO · Rakip raporu · {gun(gun_)}</b>', '<i>Dünkü katalog taramasına göre, yalnız stoktaki ürünler</i>', '']
    s.append(f'🟢 İndirime giren: <b>{son.get("dus", 0)}</b>{kiyas("dus")}')
    s.append(f'🔴 Zamlanan: <b>{son.get("art", 0)}</b>{kiyas("art")}')
    s.append(f'🆕 Yeni eklenen: <b>{son.get("yeni", 0)}</b>{kiyas("yeni")}')
    s.append(f'🟣 Stoktan çıkan: <b>{son.get("bitti", 0)}</b>{kiyas("bitti")}')
    s.append(f'🟡 Tükenmek üzere: <b>{len(d.get("hizli", []))}</b>')
    tp = [x for x in d.get('toplu', []) if x['gun'] == gun_]
    if tp:
        s += ['', '<b>📣 Toplu fiyat değişikliği (kampanya işareti)</b>']
        for x in tp:
            if x['tur'] == 'tek':
                s.append(f'• <b>{e(x["m"])}</b>: {x["n"]} ürünü tek fiyata çekti: {tl(x["fiyat"])}')
            else:
                s.append(f'• <b>{e(x["m"])}</b>: {x["n"]} ürüne {"indirim" if x["tur"] == "dus" else "zam"} (ortalama %{abs(x["orta"]):.0f})')
    # satış tahmini
    try:
        st = t.coz(os.path.join(DATA, 'satis_toplu.bin'), o); gg = [g for g in st['gunler'] if g]
        sg = sorted([x for x in gg[-1] if x['marka'] not in sup and x['marka'] not in ('Tudors', 'Tommylife', 'Aura Moda')], key=lambda x: -x['adet'])[:8]
        if sg:
            s += ['', '<b>💰 Son 24 saatte en çok satan rakipler</b> <i>(stoktaki düşüşe göre tahmin)</i>']
            for i, x in enumerate(sg, 1):
                en = next((y for y in (x.get('en_cok') or []) if not aksesuar(y[0])), None)
                s.append(f'{i}. <b>{e(x["marka"])}</b> — ~{x["adet"]} adet, ~{tl(x["ciro"])}')
                if en and en[0]:
                    s.append(f'   └ en çok: {e(kisa(en[0], 52))} ({en[1]} adet, {tl(en[2])})')
            if sup:
                s.append(f'<i>Stok sayısı güvenilmeyen markalar sayılmadı: {e(", ".join(sorted(sup)))}</i>')
    except Exception as ex:
        print('satış okunamadı:', ex)
    bl.append(s)
    # 2) indirim ve zamlar
    s = []
    dus = [x for x in d.get('dus', []) if x.get('tarih') == gun_][:10]
    if dus:
        s += ['<b>🟢 Dünün en büyük indirimleri</b>']
        s += [f'• <b>{e(x["m"])}</b> · <a href="{e(x["l"])}">{e(kisa(x["u"]))}</a>\n   {tl(x["onceki"])} → <b>{tl(x["yeni"])}</b> ({x["yuzde"]:+.0f}%)' for x in dus]
    art = [x for x in d.get('art', []) if x.get('tarih') == gun_][:6]
    if art:
        s += ['', '<b>🔴 Dünün en büyük zamları</b>']
        s += [f'• <b>{e(x["m"])}</b> · <a href="{e(x["l"])}">{e(kisa(x["u"]))}</a>\n   {tl(x["onceki"])} → <b>{tl(x["yeni"])}</b> ({x["yuzde"]:+.0f}%)' for x in art]
    md = {}
    for x in [x for x in d.get('dus', []) if x.get('tarih') == gun_]:
        md[x['m']] = md.get(x['m'], 0) + 1
    if md:
        s += ['', 'En çok indirim yapan: ' + ', '.join(f'{e(m)} {n}' for m, n in sorted(md.items(), key=lambda z: -z[1])[:6])]
    if s: bl.append(s)
    # 3) stok
    s = []
    hz = d.get('hizli', [])[:10]
    if hz:
        s += ['<b>🟡 Çok satıp tükenmek üzere</b> <i>(rakibin çok satanları)</i>']
        s += [f'• <b>{e(x["m"])}</b> · <a href="{e(x["l"])}">{e(kisa(x["u"]))}</a> {tl(x["f"])}\n   {x["stok"]:.0f} adet kaldı, günde ~{x["gunluk"]:.0f} satıyor' for x in hz]
    bt = [x for x in d.get('bitti', []) if x.get('tarih') == gun_]
    if bt:
        mb = {}
        for x in bt: mb[x['m']] = mb.get(x['m'], 0) + 1
        s += ['', f'<b>🟣 Dün stoktan çıkan {len(bt)} ürün</b>', ', '.join(f'{e(m)} {n}' for m, n in sorted(mb.items(), key=lambda z: -z[1])[:8])]
        s += [f'• <b>{e(x["m"])}</b> · <a href="{e(x["l"])}">{e(kisa(x["u"]))}</a> {tl(x["f"])}' for x in bt[:6]]
    if s: bl.append(s)
    # 4) yeni ürünler
    s = []
    ys = d.get('yeni_son', [])
    if ys:
        my = {}
        for x in ys: my[x['m']] = my.get(x['m'], 0) + 1
        s += [f'<b>🆕 Dün eklenen {len(ys)} yeni ürün</b>', ', '.join(f'{e(m)} {n}' for m, n in sorted(my.items(), key=lambda z: -z[1])[:10]), '']
        sec, gor = [], set()
        for x in sorted(ys, key=lambda z: -my[z['m']]):
            if list(gor).count(x['m']) or len(sec) >= 10: continue
            gor.add(x['m']); sec.append(x)
        s += [f'• <b>{e(x["m"])}</b> · <a href="{e(x["l"])}">{e(kisa(x["u"]))}</a> {tl(x["f"])}' for x in sec]
    ym = sorted((d.get('yeni_marka') or {}).items(), key=lambda x: -x[1])[:6]
    if ym:
        s += ['', 'Son 7 günde en çok ürün ekleyen: ' + ', '.join(f'{e(m)} {n}' for m, n in ym)]
    s += ['', f'<a href="{SITE}">Ayrıntılar sitede →</a>']
    bl.append(s)
    # mesajlara böl
    out, cur = [], ''
    for b in bl:
        txt = '\n'.join(b)
        if cur and len(cur) + len(txt) + 2 > 3900:
            out.append(cur); cur = txt
        else:
            cur = (cur + '\n\n' + txt) if cur else txt
    if cur: out.append(cur)
    return out


def main():
    mlar = mesaj()
    if '--dene' in sys.argv:
        print('\n\n=====\n\n'.join(mlar)); print([len(m) for m in mlar]); return
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
    for m in mlar:
        veri = urllib.parse.urlencode({'chat_id': chat, 'text': m, 'parse_mode': 'HTML', 'disable_web_page_preview': 'true'}).encode()
        r = json.load(urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage', veri, timeout=30))
        print('gönderildi' if r.get('ok') else r)


if __name__ == '__main__':
    main()
