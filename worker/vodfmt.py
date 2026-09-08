import re
h = open('D:/wikival-work/vlr_660370.html', encoding='utf-8').read()
pats = [r'youtu\.be/[A-Za-z0-9_-]{6,}', r'youtube\.com/watch\?v=[A-Za-z0-9_-]{6,}',
        r'href="([^"]*vod[^"]*)"']
for p in pats:
    print(p, '->', sorted(set(re.findall(p, h)))[:8])
