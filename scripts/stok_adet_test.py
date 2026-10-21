#!/usr/bin/env python3
"""Hangi rakip stok ADEDİNİ açık veriyor (günlük stok düşüşünden satış tahmini için)."""
import json, re, sys, os, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import katalog as k, yeni_urun as yu
F = {"CategoryIdList": [], "BrandIdList": [], "SupplierIdList": [], "TagIdList": [], "TagId": -1, "FilterObject": [], "MinStockAmount": -1,
     "IsShowcaseProduct": -1, "IsOpportunityProduct": -1, "FastShipping": -1, "IsNewProduct": -1, "IsDiscountedProduct": -1, "IsShippingFree": -1,
     "IsProductCombine": -1, "MinPrice": 0, "MaxPrice": 0, "SearchKeyword": "", "StrSearch": "", "StrProductIds": "", "IsSimilarProductActive": False,
     "CategoryIdSearch": -1, "IsLabelActive": False, "ShowList": 1, "LabelIds": "", "IncludeAllCategoryProducts": True}
for key, marka, site, alt in k.MARKALAR:
    try:
        if alt == 'ticimax':
            P = {"PageItemCount": 5, "PageNumber": 1, "OrderBy": "KATEGORISIRA", "OrderDirection": "ASC"}
            u = site + '/api/product/GetProductList?c=trtry0000&FilterJson=' + urllib.parse.quote(json.dumps(F)) + '&PagingJson=' + urllib.parse.quote(json.dumps(P)) + '&CreateFilter=false&TransitionOrder=0&PageType=1&PageId=0'
            p = (json.loads(k.get(u)).get('products') or [{}])[0]
            alan = {a: v for a, v in p.items() if re.search(r'(?i)stock|stok|amount|adet|quantity|sale|satis|sold', a)}
            print(marka, 'ticimax', json.dumps(alan, ensure_ascii=False)[:400], flush=True)
        elif alt == 'shopify':
            p = json.loads(k.get(site + '/products.json?limit=1'))['products'][0]
            v = p['variants'][0]; print(marka, 'shopify', {a: v.get(a) for a in v if re.search('inventory|available|quantity', a)}, flush=True)
        else:
            urls = sorted(yu.sitemap(site.split('//')[1]))[:40:8]
            for u in urls[:3]:
                txt, _ = yu.get(u, 'text/html')
                m = re.findall(r'"(stockCount|stock_count|stockQuantity|quantity|inventory_quantity|totalStock|stock)"\s*:\s*"?(-?\d+)', txt)
                print(marka, alt, u[-40:], m[:8], flush=True)
    except Exception as e:
        print(marka, alt, 'hata', str(e)[:80], flush=True)
