#!/usr/bin/env python3
"""Toptancının aynı ürünü (farklı renk ya da tekrar paylaşım) birden çok kez atmasını tek ürün olarak gruplar.
Kural: aynı kanalda aynı ürün kodu (KOD: 1028, HECTOR 2913, CODE 0050, S-806, MODEL:DİLLİ, 50705...) ya da kodu olmayan
gönderilerde fotoğraf benzerliği çok yüksek ve aynı türde. Çıktı: data/tg_grup.bin (şifreli) {ürün id: grup id}.
Görüntü vektörleri data/tg_vek.npz'de saklanır (her gün yalnız yeni ürünler hesaplanır)."""
import os, re, sys
import datetime as dt
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tg_eslestir as tg, tg_otomatik as ot, gomme
from artifact_tel import tur as urun_turu

DATA = tg.DATA
VEK = os.path.join(DATA, 'tg_vek.npz')
ESIK = float(os.environ.get('TG_GRUP_ESIK', '0.95'))
KODRX = [r'(?:KOD|CODE|MODEL|HECTOR)\s*[:.]?\s*([A-Z0-9][A-Z0-9-]{1,14})', r'(?m)^\s*([A-Z]{0,2}-?\d{3,6})\s*$']


def kod(metin):
    m = (metin or '').upper().replace('İ', 'I').replace('\xa0', ' ')
    for rx in KODRX:
        x = re.search(rx, m)
        if x and not re.fullmatch(r'\d{1,2}', x.group(1)) and x.group(1) not in ('ASPOLL', 'HECTOR', 'NEW', 'RPT'):
            return x.group(1).strip('-')
    return None


def vektorler(o, ids, U):
    eski = {}
    if os.path.exists(VEK):
        z = np.load(VEK, allow_pickle=False); eski = dict(zip(z['ids'].tolist(), z['v']))
    model = None
    for i in ids:
        if i in eski or i not in U:
            continue
        model = model or gomme.Model()
        q = ot.foto_vektor(model, U[i]['fotolar'][:3])
        if q is not None:
            v = q.mean(0); eski[i] = (v / np.linalg.norm(v)).astype(np.float16)
    np.savez_compressed(VEK, ids=np.array(list(eski)), v=np.stack(list(eski.values())))
    return eski


def main():
    o = tg.ozel_anahtar(); S = tg.sonuclar(o); U = {u['id']: u for u in tg.urunler(o)}
    V = vektorler(o, [r['id'] for r in S], U)
    ana = {r['id']: r['id'] for r in S}
    def bul(x):
        while ana[x] != x:
            ana[x] = ana[ana[x]]; x = ana[x]
        return x
    def bir(a, b): ana[bul(a)] = bul(b)
    zaman = lambda r: dt.datetime.fromisoformat(r['tarih']) if r.get('tarih') else None
    bilgi = {r['id']: (r['kanal'], kod(r.get('metin')), zaman(r), urun_turu((r.get('ozet') or '') + ' ' + (r.get('metin') or '')) , r.get('tur') or '') for r in S}
    ids = [r['id'] for r in S]
    for x in range(len(ids)):
        a = ids[x]; ka, kda, ta, tra, ra = bilgi[a]
        for y in range(x + 1, len(ids)):
            b = ids[y]; kb, kdb, tb, trb, rb = bilgi[b]
            if ka != kb or not ta or not tb:
                continue
            gun = abs((ta - tb).days)
            if kda and kdb:
                if kda == kdb and gun <= 150: bir(a, b)
                continue
            if gun > 45 or a not in V or b not in V:
                continue
            t1 = ra or (tra if tra not in ('diger', 'aksesuar') else ''); t2 = rb or (trb if trb not in ('diger', 'aksesuar') else '')
            if t1 and t2 and t1 != t2:
                continue
            if float(np.dot(V[a].astype(np.float32), V[b].astype(np.float32))) >= ESIK:
                bir(a, b)
    # grup kimliği: grubun en yeni gönderisi
    gr = {}
    for i in ids: gr.setdefault(bul(i), []).append(i)
    tar = {r['id']: r.get('tarih') or '' for r in S}
    sonuc = {}
    for uy in gr.values():
        bas = max(uy, key=lambda i: tar[i])
        for i in uy: sonuc[i] = bas
    open(os.path.join(DATA, 'tg_grup.bin'), 'wb').write(tg.sifrele(sonuc, o))
    n = sum(1 for v in gr.values() if len(v) > 1)
    print(len(S), 'gönderi ->', len(gr), 'ürün;', n, 'grupta birden çok gönderi var')
    return gr


if __name__ == '__main__':
    main()
