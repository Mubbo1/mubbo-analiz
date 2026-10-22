#!/usr/bin/env python3
"""Fiyat karşılaştırma sayfasındaki gömülü telefon kataloğunu (kat-text) yeniler.
Kullanım: python3 scripts/artifact_tel_sayfa.py <mevcut index.html> <kat.json> <çıktı index.html>
"""
import base64, gzip, re, sys
h = open(sys.argv[1]).read()
b64 = base64.b64encode(gzip.compress(open(sys.argv[2], 'rb').read(), 9)).decode()
h, n = re.subn(r'(<script id="kat-text" type="text/plain">)[^<]*(</script>)', lambda m: m.group(1) + b64 + m.group(2), h, count=1)
assert n == 1, 'kat-text bulunamadı'
open(sys.argv[3], 'w').write(h)
print('tamam', round(len(h) / 1e6, 2), 'MB')
