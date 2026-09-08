import json, glob
ck = sorted(glob.glob('D:/wikival-work/checkpoints/obs_*.json'))
print('checkpoints:', [c.split('\\')[-1] for c in ck])
obs = json.load(open(ck[0], encoding='utf-8'))
print('n obs:', len(obs), 't range:', obs[0]['_t'], '-', obs[-1]['_t'])
print('--- janela round 1 (175-290s), passo 5s ---')
for o in obs:
    if 175 <= o['_t'] <= 290 and (int(o['_t']) % 5 == 0):
        print(f"t={o['_t']:.0f} placar={o['scoreA']}-{o['scoreB']} live={o['timer_visible']}")
print('--- rounds detectados no segmento 1 (primeiros 3) ---')
fin = json.load(open('D:/wikival-work/checkpoints/final.json', encoding='utf-8'))
for s in fin['segments']:
    print(f"mapa{s['map_idx']}: {s['end_score']} t_end={s['t_end']:.0f}s n={len(s['rounds'])}")
    for r in s['rounds'][:3]:
        ts = r['timestamps']
        print(f"  R{r['roundNumber']}: buy={ts['buyPhaseStart']} start={ts['roundStart']} end={ts['roundEnd']} -> {r['result']['scoreAfterRound']}")
