import sys, json
sys.path.insert(0, 'scripts')
import telegram as tg
out = []
for k in tg.KANALLAR:
    try:
        baslik, ps = tg.sayfa(k)[:2] if isinstance(tg.sayfa(k), tuple) else (None, tg.sayfa(k))
        ps = sorted(ps, key=lambda p: p['id'])
        out.append(f"{k}: {len(ps)} paylaşım; son: " + ' | '.join(f"{p['id']} {str(p.get('tarih'))[:16]} foto={len(p.get('fotolar') or [])}" for p in ps[-4:]))
    except Exception as e:
        out.append(f'{k}: HATA {e}')
for k in ['HabbeeUnisex', 'habbeeunisex', 'habbe_unisex', 'habbeunisex']:
    try:
        t = tg.get('https://t.me/' + k)
        import re
        out.append(k + ' sayfa: ' + ' '.join(re.findall(r'<meta property="og:(?:title|description)" content="([^"]*)"', t))[:200])
    except Exception as e:
        out.append(k + ' HATA ' + str(e))
open('deneme.txt', 'w').write('\n'.join(out))
