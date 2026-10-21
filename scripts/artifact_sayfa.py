#!/usr/bin/env python3
"""Fiyat karşılaştırma sayfasının (Claude Artifact) index.html'ini yeni katalog dosyalarıyla günceller.
Kullanım: python3 scripts/artifact_sayfa.py <mevcut index.html> <ozet.json> <assets.json> <çıktı index.html>
- assets.json: {"abluka": "/_blob/...", ...} (yeni yüklenen katalog_<anahtar>.js dosyalarının adresleri)
Yalnız BRANDS dizisi (ürün sayıları) ve ASSETS haritası değişir; sayfanın geri kalanına dokunulmaz.
"""
import json, re, sys
h = open(sys.argv[1]).read(); ozet = json.load(open(sys.argv[2])); yeni = json.load(open(sys.argv[3]))
m = re.search(r'const ASSETS = (\{.*?\});', h, re.S); eski = json.loads(m.group(1))
eski.update(yeni)
h = h[:m.start()] + 'const ASSETS = ' + json.dumps(eski) + ';' + h[m.end():]
ozet.sort(key=lambda r: -r[2])
br = ','.join(json.dumps([r[0], r[1], r[2]], ensure_ascii=False) for r in ozet)
h, n = re.subn(r'const BRANDS = \[\n.*?\n\]\.map', lambda _: 'const BRANDS = [\n' + br + '\n].map', h, count=1, flags=re.S)
assert n == 1
open(sys.argv[4], 'w').write(h)
print('tamam', len(yeni), 'katalog')
