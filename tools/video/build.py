# -*- coding: utf-8 -*-
"""台本データから動画を組み立てる。

使い方:
  python3 build.py --out out/ep01 --fonts /path/to/fonts --backend openjtalk --voices /path/to/htsvoice
  python3 build.py --out out/ep01 --fonts /path/to/fonts --backend voicevox

キャラ立ち絵はリポジトリの index.html に埋め込まれた base64 画像をそのまま使う。
"""
import argparse, base64, io, json, os, re, subprocess, sys, wave
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
from render import Renderer, Fonts        # noqa: E402
from tts import make_tts, SR              # noqa: E402
from sfx import se                        # noqa: E402

PAUSE_RE = re.compile(r"［間([0-9.]+)］")
FPS = 30
GAP_LINE = 0.45      # 台詞と台詞のあいだ
GAP_CHUNK = 0.12     # 同一台詞内のチャンク間
MAX_CHUNK = 44       # 字幕1チャンクの目安文字数


def load_chars(index_html):
    s = open(index_html, encoding="utf-8").read()
    m = re.search(r"const IMAGES = (\{.*?\});", s, flags=re.S)
    out = {}
    for k, v in json.loads(m.group(1)).items():
        out[k] = Image.open(io.BytesIO(base64.b64decode(v.split(",", 1)[1]))).convert("RGBA")
    return out


def split_chunks(text):
    """［間x.x］で分割し、長い部分は句点で追加分割。[(text, pre_pause, pause_after), ...] を返す。"""
    parts = PAUSE_RE.split(text)
    items = []
    lead = 0.0
    # parts: text, pause, text, pause, ... text
    for i in range(0, len(parts), 2):
        t = parts[i].strip()
        p = float(parts[i + 1]) if i + 1 < len(parts) else 0.0
        if t:
            items.append([t, lead, p]); lead = 0.0
        elif items:
            items[-1][2] += p
        else:
            lead += p
    # 長いチャンクを句点で割る
    out = []
    for t, pre, p in items:
        if len(t) <= MAX_CHUNK or "。" not in t.rstrip("。"):
            out.append((t, pre, p)); continue
        sents = [x for x in re.split(r"(?<=。)", t) if x]
        buf = ""; first = True
        for s_ in sents:
            if buf and len(buf) + len(s_) > MAX_CHUNK:
                out.append((buf, pre if first else 0.0, 0.0)); buf = s_; first = False
            else:
                buf += s_
        if buf:
            out.append((buf, pre if first else 0.0, p))
    return out


def silence(sec):
    return np.zeros(int(SR * sec), dtype=np.float32)


def normalize(x, peak=0.89):
    m = np.abs(x).max() if len(x) else 0
    return x * (peak / m) if m > 0 else x


class Builder:
    def __init__(self, args, events, cast, source, title):
        self.args = args
        self.events = events
        self.out = args.out
        os.makedirs(os.path.join(self.out, "frames"), exist_ok=True)
        os.makedirs(os.path.join(self.out, "tts_cache"), exist_ok=True)
        chars = load_chars(args.index)
        self.R = Renderer(chars, cast, Fonts(args.fonts), source, title)
        self.tts = make_tts(args.backend, **({"voice_dir": args.voices} if args.backend == "openjtalk" else {}))
        self.frames = []      # (path, duration)
        self.audio = []       # np arrays
        self.scene = "stage"
        self.n = 0
        self.t = 0.0
        self.timeline = []

    def push(self, img, audio):
        dur = len(audio) / SR
        dur = max(round(dur * FPS) / FPS, 1 / FPS)
        need = int(round(dur * SR))
        if len(audio) < need:
            audio = np.concatenate([audio, np.zeros(need - len(audio), dtype=np.float32)])
        else:
            audio = audio[:need]
        p = os.path.join(self.out, "frames", f"f{self.n:05d}.png")
        img.save(p, compress_level=1)
        self.frames.append((p, dur)); self.audio.append(audio)
        self.n += 1; self.t += dur

    def synth(self, speaker, text):
        key = re.sub(r"[^\w]", "", f"{self.args.backend}_{speaker}_{text}")[:120]
        cp = os.path.join(self.out, "tts_cache", key + ".npy")
        if os.path.exists(cp):
            return np.load(cp)
        x = self.tts.synth(speaker, text)
        if len(x) < SR // 20:          # 記号だけの台詞（「……」など）は音素が無いので短い無音にする
            x = silence(0.35)
        x = normalize(x, 0.8)
        np.save(cp, x)
        return x

    def run(self):
        pending_se = None
        for ev in self.events:
            kind = ev[0]
            if kind == "scene":
                self.scene = ev[1] if len(ev) == 2 else f"{ev[1]}:{ev[2]}"
            elif kind == "se":
                pending_se = se(ev[1])
            elif kind == "telop":
                text, dur = ev[1], ev[2]
                img = self.R.frame_telop(text, self.scene)
                a = silence(dur)
                if pending_se is not None:
                    n = min(len(a), len(pending_se)); a[:n] += pending_se[:n]; pending_se = None
                self.timeline.append((self.t, "telop", text))
                self.push(img, a)
            elif kind == "tally":
                _, title, hero, irr, note = ev
                img = self.R.frame_tally(title, hero, irr, note)
                a = silence(3.0)
                if pending_se is not None:
                    n = min(len(a), len(pending_se)); a[:n] += pending_se[:n]; pending_se = None
                self.timeline.append((self.t, "tally", title))
                self.push(img, a)
            elif kind in ("line", "quote"):
                _, spk, text = ev
                self.timeline.append((self.t, spk, text[:30]))
                chunks = split_chunks(text) if kind == "line" else [(text, 0.0, 0.0)]
                for i, (ct, pre, pause) in enumerate(chunks):
                    if kind == "quote":
                        img = self.R.frame_quote(spk, ct)
                    else:
                        img = self.R.frame_line(spk, ct, self.scene)
                    a = self.synth(spk, ct) if ct else silence(0.01)
                    tail = pause + (GAP_LINE if i == len(chunks) - 1 else GAP_CHUNK)
                    a = np.concatenate([silence(pre), a, silence(tail)])
                    if pending_se is not None:
                        n = min(len(a), len(pending_se)); a[:n] += pending_se[:n]; pending_se = None
                    self.push(img, a)
            else:
                raise ValueError(ev)
        self.finish()

    def finish(self):
        audio = normalize(np.concatenate(self.audio), 0.9)
        wav = os.path.join(self.out, "audio.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((audio * 32767).astype(np.int16).tobytes())
        lst = os.path.join(self.out, "frames.txt")
        with open(lst, "w") as f:
            for p, d in self.frames:
                f.write(f"file '{p}'\nduration {d:.4f}\n")
            f.write(f"file '{self.frames[-1][0]}'\n")
        mp4 = os.path.join(self.out, "episode.mp4")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wav,
               "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-tune", "stillimage", "-r", str(FPS),
               "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", mp4]
        subprocess.run(cmd, check=True)
        with open(os.path.join(self.out, "timeline.txt"), "w") as f:
            for t, who, txt in self.timeline:
                f.write(f"{int(t//60):02d}:{int(t%60):02d}  {who:8s} {txt}\n")
        print("done:", mp4, f"{self.t/60:.1f} min, {self.n} frames")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default="ep01_b_script")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--index", default=os.path.join(os.path.dirname(__file__), "..", "..", "index.html"))
    ap.add_argument("--backend", default="openjtalk", choices=["openjtalk", "voicevox"])
    ap.add_argument("--voices", default=None, help="htsvoice ディレクトリ（openjtalk 用）")
    ap.add_argument("--thumbnail", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="先頭Nイベントだけ組む（確認用）")
    args = ap.parse_args()
    mod = __import__(args.script)
    events = mod.EVENTS[:args.limit] if args.limit else mod.EVENTS
    b = Builder(args, events, mod.CAST, mod.SOURCE, mod.TITLE)
    if args.thumbnail:
        b.R.thumbnail("英雄？ 無責任？", "走れメロス ─ 2対2、決めるのは、あなた", ["shin", "mamoru"], ["riku", "yume"]).save(os.path.join(args.out, "thumbnail.png"))
    b.run()


if __name__ == "__main__":
    main()
