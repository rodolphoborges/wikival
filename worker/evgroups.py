import re, urllib.request
url = 'https://www.vlr.gg/event/2860/vct-2026-americas-stage-1/group-stage'
r = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
h = urllib.request.urlopen(r, timeout=60).read().decode('utf-8')
open('D:/wikival-work/vlr_group.html', 'w', encoding='utf-8').write(h)
ms = sorted(set(re.findall(r'/(\d{6})/([\w-]+)', h)))
print(len(ms))
for m in ms:
    print(m)
