import sys, re, glob, urllib.request, collections
sys.path.insert(0, 'scripts')
import tg_eslestir as t
o = t.ozel_anahtar(); ornek = {}
for f in sorted(glob.glob('data/katalog/*.bin')):
    for r in t.coz(f, o):
        g = r.get('g') or ''
        d = re.sub(r'^https?://([^/]+).*', r'\1', g)
        if g.startswith('http') and d not in ornek: ornek[d] = g
def kucuk(u):
    if '/cdn-cgi/image/' in u: return re.sub(r'/cdn-cgi/image/[^/]+/', '/cdn-cgi/image/width=300,quality=75,format=webp/', u)
    if 'cdn.myikas.com/images/' in u: return re.sub(r'/(\d{3,4})/([^/]+)$', r'/360/\2', u)
    if 'cdn.shopify.com' in u: return re.sub(r'([?&])width=\d+', r'\1', u) + ('&' if '?' in u else '?') + 'width=300'
    if 'qukasoft.com' in u or 'percdn.com' in u: return re.sub(r'-sw\d+sh\d+', '-sw300sh400', u)
    if 'large_default' in u: return u.replace('large_default', 'home_default')
    if 'witcdn.' in u or 'voltaj.com.tr' in u: return re.sub(r'-O\.(jpe?g|png|webp)', r'-K.\1', u)
    if 'zafoni.com/i/l/' in u: return u.replace('/i/l/', '/i/m/')
    return u
def boy(u):
    try:
        req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as r: return r.status, len(r.read())
    except Exception as e: return str(e)[:40], 0
out = []
for d, u in ornek.items():
    k = kucuk(u); a = boy(u); b = boy(k) if k != u else ('-', 0)
    out.append(f'{d}: orijinal {a} -> küçük {b}\n   {k[:150]}')
open('deneme.txt', 'w').write('\n'.join(out))
