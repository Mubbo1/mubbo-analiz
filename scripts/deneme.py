import sys, re
sys.path.insert(0, 'scripts')
import telegram as tg
out = []
for k in tg.KANALLAR:
    try: t = tg.get('https://t.me/s/' + k)
    except Exception as e: out.append(f'{k} HATA {e}'); continue
    bl = re.split(r'(?=<div class="tgme_widget_message_wrap)', t)[1:]
    for b in bl[-3:]:
        pid = re.search(r'data-post="[^"]+/(\d+)"', b); tm = re.search(r'datetime="([^"]+)"', b)
        cls = re.search(r'class="tgme_widget_message ([^"]*)"', b)
        txt = re.sub(r'<[^>]+>', ' ', re.sub(r'(?s)<svg.*?</svg>', '', b)); txt = re.sub(r'\s+', ' ', txt)
        imgs = re.findall(r"background-image:url\('([^']{0,60})", b)
        out.append(f"{k} {pid and pid.group(1)} {tm and tm.group(1)[:16]} [{cls and cls.group(1)}] img={len(imgs)} :: {txt[:220]}")
open('deneme.txt', 'w').write('\n'.join(out))
