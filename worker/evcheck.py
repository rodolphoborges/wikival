import re
h = open('D:/wikival-work/vlr_event2860.html', encoding='utf-8').read()
print('match ids:', sorted(set(re.findall(r'/(\d{6})/', h))))
tabs = re.findall(r'href="([^"]*(?:matches|series|group)[^"]*)"', h)
print('tabs:', tabs[:10])
print('has group stage:', bool(re.search(r'group stage', h, re.I)))
