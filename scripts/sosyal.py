#!/usr/bin/env python3
"""MUBBO Analiz — rakiplerin Instagram (ve bilinen TikTok) hesaplarının günlük ölçümleri.

Kaynak: SocialBlade'in herkese açık profil sayfası (takipçi, takip, gönderi, etkileşim
oranı, ortalama beğeni/yorum, not) ve son günlerin takipçi geçmişi. Her gün bir ölçüm
dosyası yazılır; site bu günlük dosyaları birleştirerek günlük takipçi kazancını gösterir.
Sonuçlar depodaki açık anahtarla şifrelenir.
"""
import datetime as dt, gzip, json, os, re, struct, time, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36'
INSTAGRAM = [["Ketench", "ketenchcom"], ["Ferell Moda", "ferellmoda"], ["Semih Kurtulmuş", "semihkurtulmusmodaa"], ["Abluka Online", "abluka.online"],
             ["Bad Bear", "badbear"], ["Bpm Wear", "bpmwear"], ["By London Butik", "bylondonmoda"], ["ByBasicMan", "bybasicman"], ["Bytagayman", "bytagayman"],
             ["Catch Jeans", "catchjeans"], ["David Gerenzo", "davidgerenzo"], ["ErdTrend", "erd.trend"], ["Flaw Wear", "flawwear"], ["Forer Wear", "forerwear"],
             ["Gangown", "gangown.go"], ["Giesto", "giesto.official"], ["Grimelange", "grimelange"], ["Hafka Giyim", "hafkagiyim"], ["JuniorCrime", "jr.crime"],
             ["Kaft", "kaft"], ["Labels Wear", "labelswearr"], ["Lazzy Shoes & Wear", "lazy_shoes"], ["Madmext", "madmext"], ["No 362 Clo", "no362clo"],
             ["NOMARC", "nomarctr"], ["Outfit-Man", "outfittman"], ["Papel Giyim", "papelgiyim"], ["Piedraman", "piedramann"], ["Respire", "respireclo"],
             ["Slatra", "slatra.official"], ["Streetbox", "streetboxcomtr"], ["Tarz Adam", "tarzadam"], ["Tarz Yeri", "tarzyericom"], ["The Champ", "thechamponline"],
             ["The Manstro", "themanstro"], ["Tommylife", "tommylifecomtr"], ["Tudors", "tudorsofficial"], ["Vamos Clo", "vamosclo"], ["Voltaj Giyim", "voltajerkekgiyim"],
             ["Wunder", "wunder"], ["Zafoni", "zafonicom"], ["DeepSEA", "deepsea.com.tr"], ["Livio Ferri", "livioferri"], ["UTT Basic", "uttbasic"]]
TIKTOK = [["Ferell Moda", "ferelmoda"], ["Semih Kurtulmuş", "semihkurtulmuss"], ["Abluka Online", "abluka.online"], ["Flaw Wear", "flawwear"],
          ["Kaft", "kaftcom"], ["Ketench", "ketench"]]   # Bpm Wear'in TikTok hesabı bulunamadı


def get(url, accept='text/html'):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept, 'Accept-Language': 'en-US,en;q=0.9'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')


def next_data(t):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', t, re.S)
    return {json.dumps(q['queryKey'][0]): q['state']['data'] for q in json.loads(m.group(1))['props']['pageProps']['trpcState']['json']['queries']} if m else {}


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def profil(platform, marka, h):
    t = get(f'https://socialblade.com/{platform}/user/{urllib.parse.quote(h)}')
    nd = next_data(t)
    u = nd.get(json.dumps([platform, 'user'])) or {}
    if not u or not u.get('followers'):
        raise RuntimeError('profil bulunamadı')
    gec = nd.get(json.dumps([platform, 'history']))   # SocialBlade geçmişi yalnızca TikTok'ta sayfaya gömülü geliyor
    st = u.get('stats') or u
    r = {'marka': marka, 'platform': platform, 'kullanici': u.get('username') or h, 'takipci': num(st.get('followers')), 'takip': num(st.get('following')),
         'gonderi': num(st.get('mediaCount') if platform == 'instagram' else st.get('videos')), 'begeni_toplam': num(st.get('likes')),
         'etkilesim': st.get('engagementRate'), 'ort_begeni': st.get('averageLikes'), 'ort_yorum': st.get('averageComments'), 'not': u.get('grade'),
         'gecmis': []}
    for g in gec or []:
        r['gecmis'].append({'tarih': str(g.get('date', ''))[:10], 'takipci': num(g.get('followers')), 'takip': num(g.get('following')),
                            'gonderi': num(g.get('mediaCount', g.get('media', g.get('videos'))))})
    return r


def sifrele(obj):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    acik = serialization.load_pem_public_key(open(os.path.join(ROOT, 'scripts', 'acik_anahtar.pem'), 'rb').read())
    k = AESGCM.generate_key(256); iv = os.urandom(12)
    w = acik.encrypt(k, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return b'MB1' + struct.pack('>H', len(w)) + w + iv + AESGCM(k).encrypt(iv, gzip.compress(json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode(), 9), None)


def main():
    bugun = (dt.datetime.utcnow() + dt.timedelta(hours=3)).strftime('%Y-%m-%d')
    out, hata, gecmisli = [], 0, 0
    for platform, liste in (('instagram', INSTAGRAM), ('tiktok', TIKTOK)):
        for marka, h in liste:
            try:
                r = profil(platform, marka, h); out.append(r); gecmisli += bool(r['gecmis'])
            except Exception as e:
                hata += 1; out.append({'marka': marka, 'platform': platform, 'kullanici': h, 'hata': str(e)[:120]})
            time.sleep(1.5)
    os.makedirs(os.path.join(DATA, 'sosyal'), exist_ok=True)
    open(os.path.join(DATA, 'sosyal', bugun + '.bin'), 'wb').write(sifrele({'tarih': bugun, 'zaman': dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z', 'hesaplar': out}))
    lp = os.path.join(DATA, 'sosyal_gunler.json')
    gunler = json.load(open(lp)) if os.path.exists(lp) else []
    if bugun + '.json' not in gunler:
        gunler.append(bugun + '.json')
    json.dump(sorted(gunler), open(lp, 'w'))
    print(f'Bitti: {len(out) - hata}/{len(out)} hesap okundu, {gecmisli} hesapta günlük geçmiş var.')


if __name__ == '__main__':
    main()
