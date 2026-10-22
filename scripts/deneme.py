import sys, json
sys.path.insert(0, 'scripts')
out = []
import katalog as k
for s in ['https://toriasman.com', 'https://www.toriasman.com']:
    try:
        r = k.ticimax(s); st = [x for x in r if not x.get('stokyok')]
        out.append(f'{s} {len(r)} urun, stokta {len(st)}'); out += [json.dumps({a: x.get(a) for a in ('u','f','e','l','adet','stokyok')}, ensure_ascii=False) for x in r[:5]]
        break
    except Exception as e: out.append(f'{s} HATA {e}')
open('deneme.txt', 'w').write('\n'.join(out))
