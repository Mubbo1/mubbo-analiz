#!/usr/bin/env python3
"""Ticimax /api/bank/GetBankInstallments ile rakiplerin taksit yaptığı bankaları çeker."""
import json, os, sys, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yeni_urun as yu
KOK = {'Ketench': 'https://ketench.com', 'Ferell Moda': 'https://www.ferellmoda.com', 'Semih Kurtulmuş': 'https://semihkurtulmusfashion.com'}
def al(url, data=None):
    h = {'User-Agent': yu.UA, 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest', 'Accept-Language': 'tr-TR,tr;q=0.9'}
    if data is not None: h['Content-Type'] = 'application/json'
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=30) as r:
        return r.read(3_000_000).decode('utf-8', 'replace')
out = {}
for m, k in KOK.items():
    out[m] = []
    for q in ['Amount=1000&MaxInstallment=12&CurrencyCode=TRY', 'amount=1000&maxInstallment=12&currencyCode=TRY', 'Amount=1000&MaxInstallment=12&CurrencyCode=TL',
              'Amount=1000&MaxInstallment=0&CurrencyCode=TRY', 'Amount=1000']:
        try:
            t = al(k + '/api/bank/GetBankInstallments?' + q); out[m].append({'q': q, 't': t[:20000]})
            if '"bankInstallments":[]' not in t: break
        except Exception as e:
            out[m].append({'q': q, 'hata': str(e)[:100]})
    try:
        t = al(k + '/api/bank/GetBankInstallments', json.dumps({'Amount': 1000, 'MaxInstallment': 12, 'CurrencyCode': 'TRY'}).encode()); out[m].append({'q': 'POST', 't': t[:20000]})
    except Exception as e:
        out[m].append({'q': 'POST', 'hata': str(e)[:100]})
    print(m, [len(x.get('t', '')) for x in out[m]], flush=True)
json.dump(out, open(os.path.join(yu.DATA, 'banka_ham3.json'), 'w'), ensure_ascii=False, indent=1)
