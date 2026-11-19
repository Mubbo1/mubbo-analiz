import sys, re
sys.path.insert(0, 'scripts')
import telegram as tg
t = tg.get('https://t.me/s/hawkkingtoptan')
bl = re.split(r'(?=<div class="tgme_widget_message_wrap)', t)[1:]
out = [f'blok {len(bl)}, html {len(t)}']
for b in bl[-3:]:
    out.append(re.sub(r'\s+', ' ', b)[:2500]); out.append('-----')
open('deneme.txt', 'w').write('\n'.join(out))
