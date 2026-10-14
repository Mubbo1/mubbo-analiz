"""Fotoğrafla arama çıktısını Artifact yayın parçalarına böler.

Kullanım: python3 scripts/foto_parcala.py <cikti_klasoru>
Her parça (en fazla ~50 MB) için `files` haritasını JSON olarak ayrı satırda yazar.
İlk parça index.html'i (file_path) taşır; katalog dosyaları büyükten küçüğe dağıtılır.
"""
import json
import os
import sys

SINIR = 50 * 1024 * 1024

kl = os.path.abspath(sys.argv[1])
dosyalar = sorted((f for f in os.listdir(kl) if f.startswith('katalog_') and f.endswith('.json')),
                  key=lambda f: -os.path.getsize(os.path.join(kl, f)))
parcalar = [[os.path.getsize(os.path.join(kl, 'index.html')), {}]]
for f in dosyalar:
    b = os.path.getsize(os.path.join(kl, f))
    for p in parcalar:
        if p[0] + b <= SINIR:
            p[0] += b
            p[1][f] = os.path.join(kl, f)
            break
    else:
        parcalar.append([b, {f: os.path.join(kl, f)}])
for i, (b, m) in enumerate(parcalar, 1):
    print(f'# parça {i}: {len(m)} dosya, {b / 1048576:.1f} MB')
    print(json.dumps(m, ensure_ascii=False))
