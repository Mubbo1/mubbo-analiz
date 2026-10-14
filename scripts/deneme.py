import sys, json
sys.path.insert(0, 'scripts')
out = []
try:
    import yeni_urun as yu
    s = sorted(yu.sitemap('erdtrend.com')); out.append(f'SITEMAP {len(s)}')
    ok = 0
    for u in s[:12]:
        try:
            r = yu.urun_sayfasi(u); ok += bool(r and r['fiyat'])
            out.append(f'URUN {u} {json.dumps(r, ensure_ascii=False)[:300]}')
        except Exception as e:
            out.append(f'URUN {u} HATA {e}')
    out.append(f'FIYATLI {ok}/12')
except Exception as e:
    out.append(f'HATA {e}')
open('deneme.txt', 'w').write('\n'.join(out))
