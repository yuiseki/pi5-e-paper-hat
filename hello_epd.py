#!/usr/bin/python3
"""最小デモ: e-Paper 中央に "Hello" を表示する (向き検証用)"""
import sys

import config

sys.path.append(config.EPAPER_LIB)

from waveshare_epd import epd2in7_V2
from PIL import Image, ImageDraw, ImageFont

epd = epd2in7_V2.EPD()
epd.init()
epd.Clear()

# 縦向きネイティブ 176x264 に描いて 180 度回転 (設置向きの都合, NOTES.md 参照)
image = Image.new("1", (epd.width, epd.height), 255)
draw = ImageDraw.Draw(image)

text = "Hello"
size = 60
while size > 10:
    font = ImageFont.truetype(
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size
    )
    bbox = draw.textbbox((0, 0), text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    if w <= epd.width - 8:
        break
    size -= 2

draw.text(
    ((epd.width - w) // 2 - bbox[0], (epd.height - h) // 2 - bbox[1]),
    text, font=font, fill=0,
)
image = image.rotate(180)
epd.display(epd.getbuffer(image))
epd.sleep()
