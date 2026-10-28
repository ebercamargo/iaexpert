"""Deformação facial 2D local: fonemas aproximados, piscadas e transparência."""
from __future__ import annotations
from pathlib import Path
import cv2
import numpy as np
from PySide6.QtGui import QImage, QPixmap

def _morph(image: np.ndarray, openness: float, blink: float) -> np.ndarray:
    h, w = image.shape[:2]
    yy, xx = np.indices((h, w), dtype=np.float32)
    mx, my = w * .49, h * .771
    rx, ry = w * .245, h * .105
    area = np.maximum(0, 1 - ((xx-mx)/rx)**2 - ((yy-my)/ry)**2)**2
    stretch = .33 + 1.65 * max(0, min(1, openness))
    new_y = yy + area * (yy-my) * (1/stretch-1)
    roundness = .12 * (1 - abs(openness-.5)*2)
    new_x = xx + area*(xx-mx)*roundness
    if blink:
        for ex in (w*.285, w*.715):
            ey = h*.495
            zone = np.maximum(0, 1 - ((xx-ex)/(w*.13))**2 - ((yy-ey)/(h*.070))**2)**2
            factor = 1 - .9*max(0, min(1, blink))
            new_y += zone*(yy-ey)*(1/factor-1)
    result = cv2.remap(image, new_x.astype(np.float32), new_y.astype(np.float32),
                       cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT_101)
    result[:,:,3] = image[:,:,3]
    return result

def _pixmap(rgba):
    h,w=rgba.shape[:2]
    qim=QImage(rgba.tobytes(), w,h,w*4,QImage.Format_RGBA8888)
    return QPixmap.fromImage(qim.copy())

class FacialFrames:
    def __init__(self, folder: Path):
        high_res = folder/"avatar-head.webp"
        original = high_res if high_res.is_file() else folder/"avatar.webp"
        image=cv2.imread(str(original),cv2.IMREAD_UNCHANGED)
        if image is None: raise FileNotFoundError(f"Arquivo do rosto ausente: {original}")
        if image.ndim != 3 or image.shape[2] != 4:
            raise ValueError("O avatar deve conter um canal alpha (RGBA).")
        image=cv2.cvtColor(image,cv2.COLOR_BGRA2RGBA)
        if image.shape[1] < 360:
            factor = max(2, round(430 / image.shape[1]))
            image = cv2.resize(image, None, fx=factor, fy=factor,
                               interpolation=cv2.INTER_LANCZOS4)
        self.width=image.shape[1]
        self.height=image.shape[0]
        self.frames=[_pixmap(_morph(image,i/12.0,0.0)) for i in range(13)]
        self.blinks=[_pixmap(_morph(image,.25,v)) for v in (.33,.75,1.)]

    def frame(self, openness, blink):
        if blink >= .18:
            return self.blinks[min(2,int(blink*3))]
        return self.frames[min(12,max(0,round(openness*12)))]
