import urllib.request, re
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36'
out=[]
for u in ['https://mubbo.com','https://www.mubbo.com','https://www.instagram.com/mubbo/','https://www.trendyol.com/sr?q=mubbo']:
    try:
        r=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':UA}),timeout=25); t=r.read(300000).decode('utf-8','replace')
        txt=re.sub(r'<[^>]+>',' ',re.sub(r'(?s)<(script|style)[^>]*>.*?</\1>','',t)); txt=re.sub(r'\s+',' ',txt)
        out.append(f'{u} {r.status} {r.geturl()} len={len(t)} metin={txt[:600]!r} meta={re.findall(r"<meta[^>]+>",t)[:6]}')
    except Exception as e: out.append(f'{u} HATA {e}')
open('deneme.txt','w').write('\n'.join(out))
