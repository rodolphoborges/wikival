import cv2, subprocess, sys, glob
sys.path.insert(0, 'worker')
from rois import ROIS_1080P, crop
TESS = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
img = cv2.imread(sys.argv[1] if len(sys.argv) > 1 else 'D:/wikival-work/frames/calib_02_714s.jpg')
s = crop(img, ROIS_1080P['map_strip'])
g = cv2.cvtColor(s, cv2.COLOR_BGR2GRAY)
g = cv2.resize(g, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
_, buf = cv2.imencode('.png', g)
for psm in [6, 7]:
    p = subprocess.run([TESS, 'stdin', 'stdout', '--psm', str(psm)], input=buf.tobytes(), capture_output=True)
    print('psm', psm, repr(p.stdout.decode('utf-8', 'ignore').strip()))
