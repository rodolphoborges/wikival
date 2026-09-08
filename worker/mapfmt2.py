import re
h = open('D:/wikival-work/vlr_660370.html', encoding='utf-8').read()
items = re.findall(r'js-map-switch[^>]*data-game-id="(\d+)"[^>]*>(.*?)</a>', h, re.S)
for gid, body in items:
    txt = re.sub(r'<[^>]+>', ' ', body)
    txt = re.sub(r'\s+', ' ', txt).strip()
    print(gid, '|', txt[:120])
