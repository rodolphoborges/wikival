import re
h = open('D:/wikival-work/vlr_group.html', encoding='utf-8').read()
i = h.find('/645474/')
print(h[i:i + 2200])
