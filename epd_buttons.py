#!/usr/bin/python3
"""ボタン動作確認デモ: KEY1-KEY4 を押すと対応する数字を全画面表示する"""
import sys
import time
import signal

import config

sys.path.append(config.EPAPER_LIB)

from waveshare_epd import epd2in7_V2
from PIL import Image, ImageDraw, ImageFont
from gpiozero import Button

# 2.7inch e-Paper HAT のキー配置
KEYS = {1: Button(5), 2: Button(6), 3: Button(13), 4: Button(19)}

epd = epd2in7_V2.EPD()
epd.init()
epd.Clear()

font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 160)
font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)


def render(text, sub):
    # 縦向き 176x264 + rotate(180) = 正面から読める向き
    image = Image.new("1", (epd.width, epd.height), 255)
    draw = ImageDraw.Draw(image)
    bbox = draw.textbbox((0, 0), text, font=font_big)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((epd.width - w) // 2 - bbox[0], (epd.height - h) // 2 - bbox[1]), text, font=font_big, fill=0)
    sb = draw.textbbox((0, 0), sub, font=font_small)
    draw.text(((epd.width - (sb[2]-sb[0])) // 2, epd.height - 30), sub, font=font_small, fill=0)
    image = image.rotate(180)
    epd.display(epd.getbuffer(image))


def cleanup(*_):
    print("cleanup: sleep")
    epd.sleep()
    sys.exit(0)


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)

render("?", "Press KEY1-KEY4")
print("ready. waiting for button press...", flush=True)

last = None
while True:
    for num, btn in KEYS.items():
        if btn.is_pressed:
            if num != last:
                print(f"KEY{num} pressed", flush=True)
                render(str(num), f"KEY{num}")
                last = num
            # 表示更新中の連打は無視される（e-Paper のリフレッシュ約2秒）
    time.sleep(0.05)
