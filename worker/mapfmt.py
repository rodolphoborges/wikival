import re
h = open('D:/wikival-work/vlr_660370.html', encoding='utf-8').read()
for m in re.finditer(r'<div class="vm-stats-game[^>]*data-game-id="(\d+)"[^>]*>(.*?)</div>\s*<div class="map">', h, re.S):
    print('game', m.group(1))
i = h.find('vm-stats-game')
print(h[i:i + 700])
