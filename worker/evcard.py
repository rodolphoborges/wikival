import re
h = open('D:/wikival-work/vlr_event2860.html', encoding='utf-8').read()
i = h.find('/660370/')
print(h[max(0, i - 1500):i + 500])
