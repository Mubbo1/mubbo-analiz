#!/usr/bin/env python3
"""Haftalık rakip raporu (her pazartesi Telegram'a). Claude kullanmaz, GitHub'da ücretsiz çalışır.
Veri: data/degisim.bin, data/satis_toplu.bin, data/sikayet_durum.bin. Gönderim telegram_ozet.main ile aynı.
Kullanım: python3 scripts/telegram_hafta.py [--dene]
"""
import os, sys
import datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_eslestir as t
import telegram_ozet as oz
from artifact_tel import aksesuar
from takip import TAKIP

DATA = t.DATA
KALDIR = {'Tudors', 'Tommylife', 'Aura Moda'}
TURAD = {'trenckot': 'Trençkot', 'kaban': 'Kaban', 'mont': 'Mont', 'yelek': 'Yelek', 'ceket': 'Ceket', 'hirka': 'Hırka', 'kazak': 'Kazak', 'sweatshirt': 'Sweatshirt',
         'polo': 'Polo', 'tisort': 'Tişört', 'gomlek': 'Gömlek', 'esofman': 'Eşofman', 'takim': 'Takım', 'jean': 'Jean', 'sort': 'Şort', 'pantolon': 'Pantolon', 'ayakkabi': 'Ayakkabı'}
e, tl, kisa, gun = oz.e, oz.tl, oz.kisa, oz.gun


def mesaj():
    o = t.ozel_anahtar(); d = t.coz(os.path.join(DATA, 'degisim.bin'), o)
    sup = set(d.get('supheli') or []) | {'Ferell Moda', 'Torias Man'} | KALDIR
    g7 = (d.get('gunluk') or [])[-7:]
    top = lambda k: sum(g.get(k, 0) for g in g7)
    bas = gun(g7[0]['gun']) if g7 else '', gun(d['tarih'])
    bl = []
    s = [f'<b>📅 MUBBO · Haftalık rakip raporu</b>', f'<i>{bas[0]} – {bas[1]}</i>', '',
         f'🟢 İndirime giren: <b>{top("dus")}</b>', f'🔴 Zamlanan: <b>{top("art")}</b>', f'🆕 Yeni eklenen: <b>{top("yeni")}</b>', f'🟣 Stoktan çıkan: <b>{top("bitti")}</b>']
    # satış: bu hafta / geçen hafta
    try:
        st = t.coz(os.path.join(DATA, 'satis_toplu.bin'), o); gg = [g for g in st['gunler'] if g]
        bu, once = gg[-7:], gg[-14:-7]
        def topla(gs):
            m, u = {}, {}
            for g in gs:
                for x in g:
                    if x['marka'] in sup or x['marka'] not in TAKIP: continue
                    m[x['marka']] = m.get(x['marka'], 0) + x['adet']
                    for ad, a, f in x.get('en_cok') or []:
                        if aksesuar(ad): continue
                        k = (x['marka'], ad); v = u.setdefault(k, [0, f]); v[0] += a; v[1] = f
            return m, u
        mb, ub = topla(bu); mo, uo = topla(once)
        s += ['', '<b>💰 En çok satan rakipler (7 gün)</b>']
        for i, (m, a) in enumerate(sorted(mb.items(), key=lambda x: -x[1])[:8], 1):
            p = mo.get(m)
            fark = f' ({"+" if a >= p else ""}{round(100 * (a - p) / p)}%)' if p else ''
            s.append(f'{i}. <b>{e(m)}</b> ~{a} adet{fark}')
        bl.append(s); s = ['<b>🔥 Haftanın en çok satan ürünleri</b>']
        for i, ((m, ad), (a, f)) in enumerate(sorted(ub.items(), key=lambda x: -x[1][0])[:10], 1):
            s.append(f'{i}. <b>{e(m)}</b> · {e(kisa(ad, 50))} — ~{a} adet, {tl(f)}')
        from collections import Counter
        gun_say = Counter(x['marka'] for g in once for x in g if x.get('en_cok'))
        markalar_once = {m for m, n in gun_say.items() if n >= 5}
        yuk = sorted([(k, v[0], v[0] - uo.get(k, [0])[0]) for k, v in ub.items() if k[0] in markalar_once and v[0] >= 8 and v[0] > uo.get(k, [0])[0]], key=lambda x: -x[2])[:6]
        if yuk:
            s += ['', '<b>📈 Satışı en çok artanlar</b> <i>(geçen haftaya göre)</i>']
            s += [f'• <b>{e(m)}</b> · {e(kisa(ad, 50))} — ' + (f'{a - fark} → <b>{a}</b> adet' if a - fark else f'<b>{a}</b> adet (yeni çıktı)') for (m, ad), a, fark in yuk]
    except Exception as ex:
        print('satış okunamadı:', ex)
    bl.append(s); s = []
    # fiyat hareketleri ve kampanyalar
    md = {}
    for x in d.get('dus', []): md[x['m']] = md.get(x['m'], 0) + 1
    tp = d.get('toplu', [])
    if md or tp:
        s.append('<b>🏷 İndirim ve kampanyalar</b>')
        if md: s.append('En çok indirim yapan: ' + ', '.join(f'{e(m)} {n}' for m, n in sorted(md.items(), key=lambda z: -z[1])[:6]))
        for x in tp[:6]:
            s.append(f'• {gun(x["gun"])} · <b>{e(x["m"])}</b>: {x["n"]} ürüne {"indirim" if x["tur"] == "dus" else "zam"} (ortalama %{abs(x["orta"]):.0f})')
    bf = [b for b in d.get('bf', []) if b.get('once_orani') is not None and b['indirim_orani'] - b['once_orani'] >= 5]
    if bf:
        s += ['', 'İndirimdeki ürün oranını artıranlar (2 haftada): ' + ', '.join(f'{e(b["marka"])} %{b["once_orani"]}→%{b["indirim_orani"]}' for b in bf[:6])]
    sh = sorted([b for b in d.get('bf', []) if b['sahte']], key=lambda b: -b['sahte'])[:5]
    if sh:
        s += ['⚠️ Önce zam yapıp sonra indirim gösteren: ' + ', '.join(f'{e(b["marka"])} ({b["sahte"]} ürün)' for b in sh)]
    ym = sorted((d.get('yeni_marka') or {}).items(), key=lambda x: -x[1])[:6]
    if ym:
        s += ['', '<b>🆕 En çok ürün ekleyen</b>: ' + ', '.join(f'{e(m)} {n}' for m, n in ym if m not in KALDIR)]
    tt = d.get('tur_trend') or {}
    ch = []
    for k, v in tt.items():
        if len(v) >= 2 and v[-2][1]:
            f = round(100 * (v[-1][1] - v[-2][1]) / v[-2][1])
            if abs(f) >= 3: ch.append((k, v[-2][1], v[-1][1], f))
    if ch:
        s += ['', '<b>📊 Fiyat trendi</b> <i>(ortanca fiyat, geçen haftaya göre)</i>']
        s += [f'• {TURAD.get(k, k)}: {tl(a)} → <b>{tl(b)}</b> ({f:+d}%)' for k, a, b, f in sorted(ch, key=lambda x: -abs(x[3]))[:6]]
    try:
        sk = t.coz(os.path.join(DATA, 'sikayet_durum.bin'), o); art = []
        for m, g in (sk.get('gecmis') or {}).items():
            if m in KALDIR or len(g) < 2: continue
            hedef = (dt.date.fromisoformat(g[-1][0]) - dt.timedelta(days=7)).isoformat()
            eski = next((x for x in reversed(g) if x[0] <= hedef), g[0])
            if g[-1][1] > eski[1]: art.append((m, g[-1][1] - eski[1]))
        if art:
            s += ['', '<b>😠 Şikâyeti artan rakipler</b>: ' + ', '.join(f'{e(m)} +{n}' for m, n in sorted(art, key=lambda x: -x[1])[:6])]
    except Exception as ex:
        print('şikâyet okunamadı:', ex)
    s += ['', f'<a href="{oz.SITE}">Ayrıntılar sitede →</a>']
    bl.append(s)
    out, cur = [], ''
    for b in bl:
        txt = '\n'.join(b)
        if not txt.strip(): continue
        if cur and len(cur) + len(txt) + 2 > 3900:
            out.append(cur); cur = txt
        else:
            cur = (cur + '\n\n' + txt) if cur else txt
    if cur: out.append(cur)
    return out


if __name__ == '__main__':
    oz.main(mesaj)
