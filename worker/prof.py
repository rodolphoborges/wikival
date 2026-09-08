import cv2, time, subprocess, sys
sys.path.insert(0, 'worker')
from rois import ROIS_1080P, crop
cap = cv2.VideoCapture('D:/wikival-work/vod_1080p.mp4')
TESS = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
ts, to = [], []
t = 1000.0
for _ in range(8):
    q = time.perf_counter()
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, f = cap.read()
    ts.append(time.perf_counter() - q)
    q = time.perf_counter()
    g = cv2.cvtColor(crop(f, ROIS_1080P['timer']), cv2.COLOR_BGR2GRAY)
    _, b = cv2.imencode('.png', g)
    subprocess.run([TESS, 'stdin', 'stdout', '--psm', '7'],
                   input=b.tobytes(), capture_output=True)
    to.append(time.perf_counter() - q)
    t += 7.0
print('seek+decode medio:', round(sum(ts) / len(ts) * 1000), 'ms')
print('tesseract medio:  ', round(sum(to) / len(to) * 1000), 'ms')
