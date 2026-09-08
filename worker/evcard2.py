import re
h = open('D:/wikival-work/vlr_group.html', encoding='utf-8').read()
i = h.find('/645474/')
print(h[max(0, i - 1200):i + 400])
