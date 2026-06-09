# pi5-e-paper-hat

Raspberry Pi 5 + Waveshare 2.7inch e-Paper HAT V2 (RS2406) で動かす
Pi Swarm 物理オンボーディング画面のコード一式。

## ファイル

| ファイル | 役割 |
|---|---|
| `config.py` | `.env` を読む共通設定ローダ |
| `.env` | 設定・機密 (gitignore)。`.env.example` をコピーして作る |
| `.env.example` | 設定テンプレート |
| `epd_onboarding.py` | メインデーモン (4ページ + 地図)。systemd で常駐 |
| `epd_map_capture.py` | headless Chromium で地図を撮影し4値量子化 |
| `hello_epd.py` | 最小デモ (向き検証) |
| `epd_buttons.py` | ボタン動作確認デモ |

関連ドキュメント (ハードウェア基礎・ネットワーク構成・rollback):
`~/src/e-Paper/NOTES.md`, `~/src/e-Paper/ONBOARDING.md`

## セットアップ

```bash
cp .env.example .env
# .env を編集して WIFI_PSK / TRACCAR_PASSWORD 等を設定
python3 epd_onboarding.py   # 手動起動 (常駐は systemd)
```

## ボタン

| キー | GPIO | 動作 |
|---|---|---|
| KEY1 | 5  | Wi-Fi QR (再押下で welcome URL QR とトグル) |
| KEY2 | 6  | network / diagnostics |
| KEY3 | 13 | k3s status |
| KEY4 | 19 | 単押し: Wi-Fi QR に戻る (ESC) / 長押し1秒: 地図 (4Gray, pi-z2-wh 追従) |

## systemd

`/etc/systemd/system/epd-onboarding.service` から起動。
`WorkingDirectory` をこのディレクトリにし、`config.py` が同階層の `.env` を読む。

```bash
sudo systemctl restart epd-onboarding
journalctl -u epd-onboarding -f
```

## 依存

apt: `python3-pil python3-numpy python3-qrcode python3-selenium chromium chromium-driver`
e-Paper lib: waveshareteam/e-Paper (`EPAPER_LIB` で指定)
地図: yuiseki.dev (Caddy + PMTiles + `toner-epaper-4gray` スタイル)
位置: traccar API (k3s, NodePort 30082)
