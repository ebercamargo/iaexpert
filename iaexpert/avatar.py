"""Avatar facial 2D em alta resolução com transparência e deformação localizada.

Não oferece rastreamento 3D nem sincronização por fonemas: a animação
acompanha a amplitude da voz e preserva o restante do rosto.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PySide6.QtGui import QImage, QPixmap


# Posições relativas ao retrato RGBA de assets/avatar-v2.webp.
# A deformação só atua perto dos lábios/olhos; testa e queixo ficam intactos.
MOUTH_X, MOUTH_Y = 0.50, 0.727
EYE_CENTERS = ((0.306, 0.443), (0.703, 0.443))


def _morph(image: np.ndarray, openness: float, blink: float) -> np.ndarray:
    h, w = image.shape[:2]
    y, x = np.indices((h, w), dtype=np.float32)
    my, mx = h * MOUTH_Y, w * MOUTH_X
    rx, ry = w * 0.185, h * 0.067
    distance = ((x - mx) / rx) ** 2 + ((y - my) / ry) ** 2
    influence = np.clip(1.0 - distance, 0.0, 1.0) ** 2
    amount = max(0.0, min(1.0, float(openness)))
    # Lábios se aproximam durante o silêncio e abrem moderadamente ao falar.
    # Escala segura: não comprimir em 1/3 nem esticar 2x como na versão anterior.
    vertical_scale = 0.57 + 0.62 * amount
    source_y = y + (y - my) * influence * (1.0 / vertical_scale - 1.0)
    source_x = x.copy()

    blinking = max(0.0, min(1.0, float(blink)))
    if blinking > 0.01:
        for ex, ey in EYE_CENTERS:
            cx, cy = w * ex, h * ey
            near = ((x - cx) / (w * 0.105)) ** 2 + ((y - cy) / (h * 0.039)) ** 2
            eye_mask = np.clip(1.0 - near, 0.0, 1.0) ** 2
            # Piscada discreta e localizada em vez de deformar todo o olho.
            source_y += (y - cy) * eye_mask * blinking * 0.56

    transformed = cv2.remap(
        image,
        source_x.astype(np.float32),
        source_y.astype(np.float32),
        interpolation=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    # Contorno da cabeça idêntico em todos os estados, sem retângulo de fundo.
    transformed[:, :, 3] = image[:, :, 3]
    return transformed


def _pixmap(rgba: np.ndarray) -> QPixmap:
    h, w = rgba.shape[:2]
    image = QImage(rgba.tobytes(), w, h, w * 4, QImage.Format_RGBA8888)
    return QPixmap.fromImage(image.copy())


class FacialFrames:
    def __init__(self, folder: Path):
        preferred = folder / "avatar-v2.webp"
        legacy = folder / "avatar-head.webp"
        original = preferred if preferred.exists() else legacy if legacy.exists() else folder / "avatar.webp"
        image = cv2.imread(str(original), cv2.IMREAD_UNCHANGED)
        if image is None:
            raise FileNotFoundError(f"Imagem do avatar não encontrada: {original}")
        if image.ndim != 3 or image.shape[2] != 4:
            raise ValueError(
                "O avatar precisa ter fundo transparente (RGBA). "
                "Atualize o projeto para obter assets/avatar-v2.webp."
            )
        image = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
        self.width, self.height = image.shape[1], image.shape[0]
        self.frames = [_pixmap(_morph(image, value / 12.0, 0.0)) for value in range(13)]
        self.blinks = [_pixmap(_morph(image, 0.15, value)) for value in (0.30, 0.65, 1.0)]

    def frame(self, openness: float, blink: float) -> QPixmap:
        """Piscadas não substituem a posição atual da boca.

        Combina apenas o recorte dos olhos com o quadro de boca já selecionado.
        """
        base = self.frames[min(12, max(0, round(openness * 12)))]
        if blink < 0.18:
            return base
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QPainter

        overlay = self.blinks[min(2, max(0, round(blink * 2)))]
        frame = QPixmap(base)
        painter = QPainter(frame)
        for ex, ey in EYE_CENTERS:
            cx, cy = int(self.width * ex), int(self.height * ey)
            rx, ry = int(self.width * .118), int(self.height * .048)
            region = QRect(cx - rx, cy - ry, rx * 2, ry * 2)
            painter.drawPixmap(region, overlay, region)
        painter.end()
        return frame