# Waveshare 2.7inch e-Paper HAT V2 セットアップメモ (pi5-w-1)

2026-06-03 セットアップ。Claude Code セッションで構築・動作確認済み。

## ハードウェア

- ホスト: pi5-w-1 (Raspberry Pi 5, Raspberry Pi OS bookworm)
- パネル: Waveshare **2.7inch e-Paper HAT V2**（基板ラベル RS2406）
- 解像度: **176 x 264**、白黒（4階調グレースケール対応）
- 接続: GPIO ヘッダ直挿し（SPI0 / CE0）

## 重要: ドライバは V2 を使うこと

```python
from waveshare_epd import epd2in7_V2   # 正
from waveshare_epd import epd2in7      # 誤 (V1)
```

**V1 ドライバ (`epd2in7`) を使うと BUSY 信号は正常に返ってきてスクリプトも
エラーなく完走するのに、画面は一切変化しない**という非常に紛らわしい挙動になる。
「動いてるのに表示されない」時はまずドライバのバージョンを疑うこと。

## SPI 設定

- `/boot/firmware/config.txt` の `dtparam=spi=on` を有効化済み（行8）
  - 設定したのは `sudo raspi-config nonint do_spi 0`（永続化）
  - 当日は `sudo dtparam spi=on` で再起動なしで即時適用した
- デバイス: `/dev/spidev0.0` を使用
- **注意**: Pi 5 には素の状態でも `/dev/spidev10.0` が存在するが、これは別系統
  （RP1 内部）であり e-Paper には使わない。`spidev0.0` が無い場合は
  `dtparam=spi=on` がコメントアウトされていないか確認
- 再起動後も SPI 有効を確認済み (2026-06-03)

## 権限

- 一般ユーザー (yuiseki) は `spi` グループ所属のため **sudo 不要**

## 表示の向き（実機検証済み）

パネルの設置向きの都合で、正面から読める向きにするには:

```python
image = Image.new("1", (epd.width, epd.height), 255)  # 176x264 縦向きネイティブ
# ... 描画 ...
image = image.rotate(180)                             # 180度回転が必須
epd.display(epd.getbuffer(image))
```

検証結果のまとめ:

| 描き方 | 見え方 |
|---|---|
| 横向き 264x176 キャンバス（getbuffer が CCW 回転） | 左に90度傾く |
| 縦向き 176x264 そのまま | 天地逆 |
| 縦向き 176x264 + `rotate(180)` | **正面から読める（正解）** |

つまり実効的な表示領域は **幅176 x 高さ264 の縦長**。

## ファイル配置

- ライブラリ: `~/src/e-Paper/RaspberryPi_JetsonNano/python/lib/`
  （https://github.com/waveshareteam/e-Paper の clone）
- 公式サンプル: `~/src/e-Paper/RaspberryPi_JetsonNano/python/examples/`
  - V2 用デモ: `epd_2in7_V2_test.py`
- 動作確認済み自作スクリプト: `~/src/hello_epd.py`
  - 縦向き + rotate(180)、テキストが幅に収まるようフォントサイズ自動縮小
  - フォント: `/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf`

## 依存パッケージ（apt、インストール済み）

python3-pip / python3-pil / python3-numpy / python3-spidev /
python3-gpiozero / python3-lgpio

## 運用メモ

- 表示後は `epd.sleep()` を呼ぶこと（省電力モード、表示は保持される）
- e-Paper は頻繁なフル更新で劣化するので、定期更新するアプリでは更新間隔に注意
  （V2 は部分更新 API `display_Partial` あり、`epd_2in7_V2_test.py` 参照）
- スクリプトを Ctrl-C 等で中断した場合、パネルが通電状態のまま残ることがある。
  その場合は `epd.sleep()` または exit ハンドラでの後始末を入れる

## HAT の4ボタン（実機検証済み 2026-06-03）

| キー | GPIO |
|---|---|
| KEY1 | GPIO5 |
| KEY2 | GPIO6 |
| KEY3 | GPIO13 |
| KEY4 | GPIO19 |

- `gpiozero` の `Button(5)` 等でそのまま読める（デフォルトの内部プルアップで OK、sudo 不要）
- 検証スクリプト: `~/src/epd_buttons.py`（押したキーの数字を全画面表示。SIGTERM/SIGINT で `epd.sleep()` する後始末つき）
- e-Paper のフル更新は約2秒かかるため、更新中の押下は反映されない点に注意
