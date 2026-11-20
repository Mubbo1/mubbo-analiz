"""Kâr analizi hesabı (site ile aynı kural): satış fiyatının içindeki %10 KDV, toptan fiyat ve ürün başı 180 TL kargo düşülür."""
KDV = 0.10
KARGO = 180


def rakip_fiyat(r):
    """Telegram ürününün rakip karşılıkları: aynı ürün varsa onlar, yoksa benzerler"""
    ref = [a for a in (r.get('ayni') or []) if a.get('fiyat')] or [a for a in (r.get('benzer') or []) if a.get('fiyat')]
    if not ref:
        return None
    f = sorted(a['fiyat'] for a in ref)
    return {'kaynak': 'ayni' if r.get('ayni') else 'benzer', 'ort': sum(f) / len(f), 'orta': f[len(f) // 2], 'min': f[0], 'max': f[-1],
            'min_m': min(ref, key=lambda a: a['fiyat'])['marka'], 'max_m': max(ref, key=lambda a: a['fiyat'])['marka'], 'marka': len({a['marka'] for a in ref})}


def oneri(toptan, rk):
    """Önerilen satış fiyatı: rakiplerin ortanca fiyatının %5 altı, sonu 9'la biter; rakip yoksa maliyetin 2 katı"""
    hedef = rk['orta'] * 0.95 if rk else (toptan + KARGO) * 2
    s = max(int(hedef // 50) * 50 - 1, 49)
    return s


def kar(toptan, satis):
    net = satis / (1 + KDV) - toptan - KARGO
    return net, 100 * net / (toptan + KARGO)
