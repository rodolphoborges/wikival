import re
h = open('D:/wikival-work/vlr_event2860.html', encoding='utf-8').read()
items = re.findall(r'<a class="bracket-item[^"]*"[^>]*title="([^"]+)" href="(/[^"]+)"', h)
print('bracket items:', len(items))
for t, u in items:
    print(t, '->', u)
print('--- labels:', re.findall(r'bracket-col-label">\s*([^<]+?)\s*<', h))
