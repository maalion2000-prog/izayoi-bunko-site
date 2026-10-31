# 十六夜文庫 動画生成パイプライン

台本データ（`ep01_b_script.py` など）から、立ち絵・字幕・引用カード・効果音つきの MP4 を組み立てる。
立ち絵はリポジトリの `index.html` に埋め込まれた base64 画像をそのまま読むので、図鑑を更新すれば動画側も追従する。

## 構成

| ファイル | 役割 |
|---|---|
| `ep01_b_script.py` | 台本データ（イベント列）。`docs/scripts/ep01-hashire-merosu-b-shin.md` を機械可読にしたもの |
| `render.py` | Pillow でフレーム描画。図鑑サイトの配色（分類色・紙色）を流用 |
| `tts.py` | 音声合成。`voicevox`（本番）と `openjtalk`（下書き）の2バックエンド |
| `sfx.py` | 効果音を numpy で合成（外部素材なし） |
| `build.py` | 全体の組み立て。字幕チャンク分割、［間x.x］の無音、ffmpeg での結合 |

## 使い方

```bash
pip install pillow numpy pyopenjtalk      # 下書き用。VOICEVOX を使う場合 pyopenjtalk は不要
# フォント: Zen Maru Gothic（Medium/Bold）と Shippori Mincho（Medium/Bold）の TTF を fonts/ に置く
#   ファイル名: ZenMaruGothic-Medium.ttf ZenMaruGothic-Bold.ttf ShipporiMincho-Medium.ttf ShipporiMincho-Bold.ttf
#   （Google Fonts から取得。無い場合は IPA ゴシックにフォールバック）

# 本番: VOICEVOX ENGINE を起動しておく（http://127.0.0.1:50021）
python3 tools/video/build.py --out out/ep01 --fonts fonts --backend voicevox --thumbnail

# 下書き: pyopenjtalk（同梱の Mei 声 + 任意で htsvoice ディレクトリ）
python3 tools/video/build.py --out out/ep01 --fonts fonts --backend openjtalk --voices /path/to/htsvoice --thumbnail

# 先頭 N イベントだけ組んで確認
python3 tools/video/build.py --out out/test --fonts fonts --backend openjtalk --limit 20
```

出力: `out/ep01/episode.mp4`、`thumbnail.png`、`timeline.txt`（台詞ごとの開始時刻。概要欄のタイムスタンプ用）、`frames/`、`audio.wav`。
音声は `tts_cache/` にキャッシュされるので、台本の一部を直しても変えた台詞だけ再合成される。

## 声の設定（`tts.py` の VOICES）

| キャラ | VOICEVOX スタイルID（案） | 話速 | ピッチ | 抑揚 |
|---|---|---|---|---|
| テル | 67（栗田まろん） | 1.05 | +0.02 | 1.15 |
| マモル | 11（玄野武宏 ノーマル） | 0.95 | −0.01 | 0.85 |
| シン | 13（青山龍星 ノーマル） | 0.90 | −0.03 | 0.80 |
| リク | 12（白上虎太郎 ふつう） | 1.20 | +0.01 | 1.30 |
| ユメ | 14（冥鳴ひまり） | 0.85 | +0.01 | 1.05 |

スタイルIDは VOICEVOX のバージョンで変わることがある。`curl http://127.0.0.1:50021/speakers` で確認して合わせる。
VOICEVOX のキャラクター音声を使う場合は、各キャラの利用規約に従い概要欄に「VOICEVOX:青山龍星」のようにクレジットを入れる。

下書き用の openjtalk バックエンドは、同梱の Mei（CC BY 3.0）と tohoku-f01（CC BY 4.0、<https://github.com/icn-lab/htsvoice-tohoku-f01>）を話速とピッチの差で5人分に割り当てている。
公開用には VOICEVOX を推奨。

## 台本データの書き方

```python
("scene", "stage")                 # cold / stage / final,<cid> / end
("telop", "テキスト", 秒)           # テロップのみ。直前に ("se", 名前) があればその効果音を重ねる
("se", "toi")                      # toi / fuda / tap / ichimoku / mochikoshi / logo
("line", "shin", "台詞。［間0.8］続き。")   # ［間x.x］で無音。長い台詞は句点で自動分割
("quote", "teru", "本文の引用")     # 引用カードを表示しつつ speaker が読む
("tally", "札上げ", ["riku","yume"], ["shin","mamoru"], "開始時 2対2")
```
