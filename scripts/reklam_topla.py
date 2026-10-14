#!/usr/bin/env python3
"""MUBBO Analiz — rakiplerin Instagram/Facebook'ta yayındaki reklamlarını Meta Reklam Kütüphanesi'nden toplar.

GitHub Actions günde bir çalıştırır (Playwright + Chromium). Her rakip için Reklam Kütüphanesi'nde
alan adıyla arama yapar, rakibin sayfa kimliklerini bulur (data/reklam_sayfalar.json'da saklanır),
sonra sayfanın tüm aktif reklamlarını kaydırarak okur. Ham sonuç depodaki açık anahtarla şifrelenip
data/reklam_ham.bin dosyasına yazılır; ürün eşleştirmesi ve sitedeki reklam dosyaları
scripts/reklam_birlestir.py ile (site şifresiyle) üretilir.

Kullanım: python3 scripts/reklam_topla.py [--deneme "Marka1,Marka2"]
"""
import asyncio, base64, datetime as dt, gzip, io, json, os, re, struct, sys, time, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import yeni_urun as yu  # RAKIPLER listesi ve sifrele()

SAYFA_DOSYA = os.path.join(DATA, 'reklam_sayfalar.json')
HAM_DOSYA = os.path.join(DATA, 'reklam_ham.bin')
HAM_KLASOR = os.path.join(DATA, 'reklam_ham')
SIRA_DOSYA = os.path.join(DATA, 'reklam_sira.json')
LIB = 'https://www.facebook.com/ads/library/'
MARKA_SURE = 120          # bir marka için en fazla saniye
MAX_REKLAM = 2500         # bir marka için en fazla reklam
GORSEL_PX = 150


def kok(host):
    host = host.lower()
    host = re.sub(r'^https?://', '', host).split('/')[0]
    return host[4:] if host.startswith('www.') else host


def yurut(o, bulunan):
    """JSON içinde ad_archive_id taşıyan tüm reklam nesnelerini topla."""
    if isinstance(o, dict):
        if 'ad_archive_id' in o and isinstance(o.get('snapshot'), dict):
            bulunan[str(o['ad_archive_id'])] = o
        for v in o.values():
            yurut(v, bulunan)
    elif isinstance(o, list):
        for v in o:
            yurut(v, bulunan)


def json_parcalari(txt):
    out = []
    for line in txt.split('\n'):
        line = line.strip()
        if line.startswith('for (;;);'):
            line = line[9:]
        if line[:1] in '{[':
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def ad_domain(ad):
    s = ad.get('snapshot') or {}
    urls = [s.get('link_url') or '', s.get('caption') or '']
    for c in s.get('cards') or []:
        urls.append(c.get('link_url') or '')
    return ' '.join(u.lower() for u in urls)


def sade(ad):
    s = ad.get('snapshot') or {}
    def g(x):
        return (x or {}).get('text') if isinstance(x, dict) else x
    kart = []
    for c in (s.get('cards') or [])[:10]:
        kart.append({'baslik': c.get('title'), 'metin': g(c.get('body')), 'link': c.get('link_url'),
                     'gorsel': c.get('resized_image_url') or c.get('original_image_url') or c.get('video_preview_image_url')})
    vid = s.get('videos') or []
    img = s.get('images') or []
    kapak = None
    if vid:
        kapak = vid[0].get('video_preview_image_url')
    elif img:
        kapak = img[0].get('resized_image_url') or img[0].get('original_image_url')
    elif kart:
        kapak = kart[0]['gorsel']
    return {
        'id': str(ad.get('ad_archive_id')), 'page_id': str(ad.get('page_id') or ''), 'page_name': ad.get('page_name') or s.get('page_name'),
        'baslangic': ad.get('start_date'), 'bitis': ad.get('end_date'), 'aktif': ad.get('is_active'),
        'adet': ad.get('collation_count') or 1, 'grup': str(ad.get('collation_id') or ''),
        'format': s.get('display_format'), 'video': bool(vid) or any((c.get('video_preview_image_url') for c in (s.get('cards') or []))),
        'metin': g(s.get('body')), 'baslik': s.get('title'), 'hedef': s.get('link_url'), 'kartlar': kart, 'kapak_url': kapak,
        'platform': ad.get('publisher_platform'),
    }


async def sayfa_oku(page, url, sure, limit, kaydir=True):
    bulunan = {}

    sayac = {'gql': 0}

    async def on_resp(resp):
        try:
            if '/api/graphql' in resp.url or 'ads/library' in resp.url:
                txt = await resp.text()
                if '/api/graphql' in resp.url:
                    sayac['gql'] += 1
                    if 'ad_archive_id' in txt:
                        sayac['adli'] = sayac.get('adli', 0) + 1
                    if os.environ.get('REKLAM_DEBUG') and len(txt) > sayac.get('enbuyuk', 0):
                        sayac['enbuyuk'] = len(txt); sayac['ornek'] = txt[:700]
                for p in json_parcalari(txt):
                    yurut(p, bulunan)
        except Exception:
            pass

    page.on('response', on_resp)
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=60000)
    except Exception as e:
        print('  açılamadı:', e)
    await page.wait_for_timeout(3500 if kaydir else 2500)
    # sayfa içi gömülü JSON
    try:
        html = await page.content()
        for m in re.finditer(r'<script type="application/json"[^>]*>(.*?)</script>', html, re.S):
            try:
                yurut(json.loads(m.group(1)), bulunan)
            except Exception:
                pass
    except Exception:
        pass
    t0 = time.time(); son = -1; ayni = 0
    while kaydir and time.time() - t0 < sure and len(bulunan) < limit:
        try:
            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            await page.mouse.wheel(0, 3000)
        except Exception:
            pass
        await page.wait_for_timeout(2000)
        if len(bulunan) == son:
            ayni += 1
            if ayni >= 8:
                break
        else:
            ayni = 0; son = len(bulunan)
    page.remove_listener('response', on_resp)
    if os.environ.get('REKLAM_DEBUG') and kaydir:
        print(f'  {len(bulunan)} reklam, {sayac["gql"]} graphql yanıtı, {sayac.get("adli", 0)} tanesinde reklam')
        print('  en büyük graphql:', sayac.get('enbuyuk'), repr(sayac.get('ornek', ''))[:700])
        try:
            print('  sayfa metni:', repr((await page.inner_text('body'))[-600:]))
        except Exception:
            pass
    return bulunan


async def tek_sorgu(page, params):
    q = urllib.parse.urlencode(params)
    return await sayfa_oku(page, LIB + '?' + q, 0, 10 ** 6, kaydir=False)


async def sayfa_tara(page, pid, sure):
    """Oturumsuz kütüphane bir sorguda en çok ~30 reklam döndürür: başlangıç tarihine göre
    haftalık, dolu haftalarda günlük aralıklarla sorgulanır."""
    temel = {'active_status': 'active', 'ad_type': 'all', 'country': 'TR', 'media_type': 'all',
             'search_type': 'page', 'view_all_page_id': pid}
    t0 = time.time(); bulunan = {}
    bugun = (dt.datetime.utcnow() + dt.timedelta(hours=3)).date()
    pencere = [(bugun - dt.timedelta(days=7 * (i + 1) - 1), bugun - dt.timedelta(days=7 * i)) for i in range(16)]
    pencere.append((dt.date(2015, 1, 1), bugun - dt.timedelta(days=7 * 16)))
    while pencere and time.time() - t0 < sure:
        a, b = pencere.pop(0)
        r = await tek_sorgu(page, dict(temel, **{'start_date[min]': a.isoformat(), 'start_date[max]': b.isoformat()}))
        bulunan.update(r)
        if len(r) >= 28 and (b - a).days >= 1:
            gun = (b - a).days + 1
            if gun > 14:
                orta = a + dt.timedelta(days=gun // 2)
                pencere[:0] = [(a, orta), (orta + dt.timedelta(days=1), b)]
            else:
                pencere[:0] = [(a + dt.timedelta(days=i), a + dt.timedelta(days=i)) for i in range(gun)]
    if pencere:
        print(f'  süre doldu, {len(pencere)} aralık kaldı')
    return bulunan


async def gorsel_indir(ctx, url):
    try:
        r = await ctx.request.get(url, timeout=20000)
        if not r.ok:
            return None
        from PIL import Image
        im = Image.open(io.BytesIO(await r.body())).convert('RGB')
        im.thumbnail((GORSEL_PX, GORSEL_PX * 2))
        o = io.BytesIO(); im.save(o, 'WEBP', quality=45)
        return 'data:image/webp;base64,' + base64.b64encode(o.getvalue()).decode()
    except Exception:
        return None


async def main():
    from playwright.async_api import async_playwright
    deneme = None
    if '--deneme' in sys.argv:
        deneme = set(x.strip() for x in sys.argv[sys.argv.index('--deneme') + 1].split(','))
    sayfalar = json.load(open(SAYFA_DOSYA)) if os.path.exists(SAYFA_DOSYA) else {}
    sonuc = {}
    # Meta, aynı sunucudan art arda gelen sorguları birkaç markadan sonra boş döndürüyor.
    # Bu yüzden her çalışma sıradaki markadan başlar, kısıtlama başlayınca durur; sonraki çalışma kaldığı yerden devam eder.
    sira = json.load(open(SIRA_DOSYA)).get('sira', 0) if os.path.exists(SIRA_DOSYA) else 0
    markalar = list(yu.RAKIPLER)
    sira %= len(markalar)
    markalar = markalar[sira:] + markalar[:sira]
    islenen = 0; bos_ard = 0
    async with async_playwright() as p:
        br = await p.chromium.launch(args=['--no-sandbox'])
        ctx = await br.new_context(locale='tr-TR', user_agent=yu.UA, viewport={'width': 1280, 'height': 2000})
        page = await ctx.new_page()
        for marka, host in markalar:
            if deneme and marka not in deneme:
                continue
            if not deneme and bos_ard >= 2:
                print(f'art arda {bos_ard} marka boş geldi (Meta kısıtlaması); kalan markalar sonraki çalışmaya')
                islenen -= bos_ard  # boş gelenler sonraki çalışmada yeniden denenir
                for _ in range(bos_ard):
                    sonuc.popitem()
                break
            islenen += 1
            # her marka için temiz bir tarayıcı oturumu ve kısa bir bekleme: art arda sorgular Meta tarafından kısılıyor
            try:
                await ctx.close()
            except Exception:
                pass
            ctx = await br.new_context(locale='tr-TR', user_agent=yu.UA, viewport={'width': 1280, 'height': 2000})
            page = await ctx.new_page()
            await page.wait_for_timeout(8000)
            k = kok(host); t0 = time.time()
            ids = sayfalar.get(marka) or []
            if not ids:
                q = urllib.parse.urlencode({'active_status': 'active', 'ad_type': 'all', 'country': 'TR', 'media_type': 'all',
                                            'q': k, 'search_type': 'keyword_unordered'})
                ads = await sayfa_oku(page, LIB + '?' + q, 45, 300)
                say = {}
                for a in ads.values():
                    if k.split('.')[0] in ad_domain(a):
                        pid = str(a.get('page_id') or '')
                        if pid:
                            say[pid] = say.get(pid, 0) + 1
                ids = [pid for pid, n in sorted(say.items(), key=lambda x: -x[1]) if n >= 2][:3]
                print(f'{marka}: arama {len(ads)} reklam, sayfa kimlikleri {ids}')
                if ids:
                    sayfalar[marka] = ids
            hepsi = {}
            for pid in ids:
                kalan = max(60, MARKA_SURE - (time.time() - t0))
                ads = await sayfa_tara(page, pid, kalan)
                for a in ads.values():
                    if str(a.get('page_id') or '') == pid:
                        hepsi[str(a['ad_archive_id'])] = sade(a)
            if ids and not hepsi:
                print(f'{marka}: boş geldi, 60 sn bekleyip yeniden deneniyor')
                await page.wait_for_timeout(60000)
                for pid in ids:
                    ads = await sayfa_tara(page, pid, 90)
                    for a in ads.values():
                        if str(a.get('page_id') or '') == pid:
                            hepsi[str(a['ad_archive_id'])] = sade(a)
            liste = list(hepsi.values())
            async def tek(r):
                r['kapak'] = await gorsel_indir(ctx, r['kapak_url']) if r.get('kapak_url') else None
                for c in r['kartlar']:
                    c['gorsel'] = None  # kart görselleri saklanmaz (boyut)
            for i in range(0, len(liste), 16):
                await asyncio.gather(*(tek(r) for r in liste[i:i + 16]))
            sonuc[marka] = liste
            bos_ard = bos_ard + 1 if (ids and not liste) else 0
            print(f'{marka}: {len(liste)} aktif reklam ({int(time.time() - t0)} sn)')
            if deneme and liste:
                x = dict(liste[0]); x['kapak'] = (x['kapak'] or '')[:60]
                print('  örnek:', json.dumps(x, ensure_ascii=False)[:1500])
        await br.close()
    json.dump(sayfalar, open(SAYFA_DOSYA, 'w'), ensure_ascii=False, indent=1)
    toplam = sum(len(v) for v in sonuc.values())
    print('toplam', toplam, 'reklam')
    if deneme:
        return
    # hiç ilerlenemediyse (baştaki markaların gerçekten reklamı yok ya da hep kısıtlı) takılmamak için 2 marka atla
    if islenen <= 0:
        islenen = 2
    json.dump({'sira': (sira + islenen) % len(yu.RAKIPLER), 'son': dt.datetime.utcnow().isoformat(timespec='seconds') + 'Z',
               'bu_calisma': list(sonuc)}, open(SIRA_DOSYA, 'w'), ensure_ascii=False)
    sonuc = {m: v for m, v in sonuc.items() if v}
    if not sonuc:
        print('hiç reklam bulunamadı; parça yazılmadı'); return
    simdi = dt.datetime.utcnow() + dt.timedelta(hours=3)
    os.makedirs(HAM_KLASOR, exist_ok=True)
    open(os.path.join(HAM_KLASOR, simdi.strftime('%Y%m%d%H%M') + '.bin'), 'wb').write(
        yu.sifrele({'tarih': simdi.strftime('%Y-%m-%d'), 'markalar': sonuc}))
    # 10 günden eski parçaları çıkar (birleştirme her gün yapılıyor; git geçmişinde durur)
    sinir = (simdi - dt.timedelta(days=10)).strftime('%Y%m%d')
    for f in os.listdir(HAM_KLASOR):
        if f[:8] < sinir:
            os.remove(os.path.join(HAM_KLASOR, f))


if __name__ == '__main__':
    asyncio.run(main())
