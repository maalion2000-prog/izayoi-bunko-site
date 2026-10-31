# -*- coding: utf-8 -*-
"""音声合成バックエンド。

- voicevox : ローカルで起動した VOICEVOX ENGINE (http://127.0.0.1:50021) を使う。本番用。
- openjtalk: pyopenjtalk (HTS voice)。エンジンを起動できない環境向けの下書き用。

どちらも 48kHz mono float32 の numpy 配列を返す。
"""
import io, json, os, re, urllib.request, wave
import numpy as np

SR = 48000

# ── キャラ別の声設定 ───────────────────────────────────────
# voicevox: speaker は VOICEVOX のスタイルID。speed/pitch/intonation は audio_query のスケール。
# openjtalk: voice は htsvoice ファイル名（None なら同梱の mei_normal）、speed と half_tone。
VOICES = {
    "teru":   dict(voicevox=dict(speaker=67, speed=1.05, pitch=0.02,  intonation=1.15),
                   openjtalk=dict(voice="tohoku-f01-happy.htsvoice",   speed=1.05, half_tone=-1.0)),
    "mamoru": dict(voicevox=dict(speaker=11, speed=0.95, pitch=-0.01, intonation=0.85),
                   openjtalk=dict(voice="tohoku-f01-neutral.htsvoice", speed=0.95, half_tone=-7.0)),
    "shin":   dict(voicevox=dict(speaker=13, speed=0.90, pitch=-0.03, intonation=0.80),
                   openjtalk=dict(voice=None,                          speed=0.90, half_tone=-9.5)),
    "riku":   dict(voicevox=dict(speaker=12, speed=1.20, pitch=0.01,  intonation=1.30),
                   openjtalk=dict(voice="tohoku-f01-happy.htsvoice",   speed=1.20, half_tone=-5.0)),
    "yume":   dict(voicevox=dict(speaker=14, speed=0.85, pitch=0.01,  intonation=1.05),
                   openjtalk=dict(voice=None,                          speed=0.85, half_tone=1.0)),
}


def _resample(x, sr):
    if sr == SR:
        return x.astype(np.float32)
    n = int(round(len(x) * SR / sr))
    xp = np.linspace(0, 1, len(x), endpoint=False)
    xq = np.linspace(0, 1, n, endpoint=False)
    return np.interp(xq, xp, x).astype(np.float32)


def _wav_bytes_to_np(b):
    with wave.open(io.BytesIO(b)) as w:
        sr = w.getframerate(); ch = w.getnchannels(); sw = w.getsampwidth()
        raw = w.readframes(w.getnframes())
    dt = {1: np.int8, 2: np.int16, 4: np.int32}[sw]
    x = np.frombuffer(raw, dtype=dt).astype(np.float32) / float(2 ** (8 * sw - 1))
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return _resample(x, sr)


class VoicevoxTTS:
    def __init__(self, host="http://127.0.0.1:50021"):
        self.host = host
        urllib.request.urlopen(host + "/version", timeout=5).read()

    def synth(self, speaker, text):
        v = VOICES[speaker]["voicevox"]
        q = urllib.request.Request(f"{self.host}/audio_query?speaker={v['speaker']}&text={urllib.parse.quote(text)}", method="POST")
        query = json.loads(urllib.request.urlopen(q, timeout=60).read())
        query["speedScale"] = v["speed"]; query["pitchScale"] = v["pitch"]; query["intonationScale"] = v["intonation"]
        query["prePhonemeLength"] = 0.05; query["postPhonemeLength"] = 0.1
        query["outputSamplingRate"] = SR
        r = urllib.request.Request(f"{self.host}/synthesis?speaker={v['speaker']}", data=json.dumps(query).encode(),
                                   headers={"Content-Type": "application/json"}, method="POST")
        return _wav_bytes_to_np(urllib.request.urlopen(r, timeout=120).read())


class OpenJTalkTTS:
    def __init__(self, voice_dir=None):
        import pyopenjtalk
        self.pj = pyopenjtalk
        self.voice_dir = voice_dir
        self.engines = {}

    def _engine(self, voice):
        if voice is None:
            return None
        if voice not in self.engines:
            path = os.path.join(self.voice_dir, voice) if self.voice_dir else voice
            self.engines[voice] = self.pj.HTSEngine(path.encode() if isinstance(path, str) else path)
        return self.engines[voice]

    def synth(self, speaker, text):
        v = VOICES[speaker]["openjtalk"]
        # 記号だけ（「……」など）は音素が無く、エンジンが落ちることがあるので無音を返す
        if not re.search(r"[ぁ-んァ-ヶ一-龠々0-9０-９A-Za-z]", text):
            return np.zeros(int(SR * 0.3), dtype=np.float32)
        eng = self._engine(v["voice"])
        if eng is None:
            x, sr = self.pj.tts(text, speed=v["speed"], half_tone=v["half_tone"])
        else:
            labels = self.pj.extract_fullcontext(text)
            eng.set_speed(v["speed"]); eng.add_half_tone(v["half_tone"])
            x = eng.synthesize(labels); sr = eng.get_sampling_frequency()
        x = np.asarray(x, dtype=np.float32)
        if np.abs(x).max() > 1.5:   # int16 スケールで返る実装への保険
            x = x / 32768.0
        return _resample(x, sr)


def make_tts(backend, **kw):
    if backend == "voicevox":
        return VoicevoxTTS(**kw)
    return OpenJTalkTTS(**kw)


import urllib.parse  # noqa: E402  (VoicevoxTTS で使用)
