# -*- coding: utf-8 -*-
"""効果音を numpy で合成する（外部素材を使わない）。48kHz mono float32。"""
import numpy as np
SR = 48000


def _tone(freq, dur, amp=0.3, decay=4.0, harmonics=(1.0, 0.35, 0.15)):
    t = np.arange(int(SR * dur)) / SR
    env = np.exp(-decay * t)
    y = sum(a * np.sin(2 * np.pi * freq * (i + 1) * t) for i, a in enumerate(harmonics))
    return (amp * env * y).astype(np.float32)


def _mix(*parts):
    n = max(len(p) for p in parts)
    out = np.zeros(n, dtype=np.float32)
    for p in parts:
        out[:len(p)] += p
    return out


def _delay(x, sec):
    return np.concatenate([np.zeros(int(SR * sec), dtype=np.float32), x])


def se(name):
    if name == "toi":          # 問い：二音の澄んだチャイム
        return _mix(_tone(880, 1.4, 0.22, 3.0), _delay(_tone(1318.5, 1.6, 0.2, 2.5), 0.18))
    if name == "fuda":         # 札：木の軽い打音
        n = int(SR * 0.12); t = np.arange(n) / SR
        noise = np.random.default_rng(1).normal(0, 1, n) * np.exp(-60 * t)
        body = np.sin(2 * np.pi * 420 * t) * np.exp(-40 * t)
        return (0.35 * (0.4 * noise + body)).astype(np.float32)
    if name == "tap":          # テロップ：小さなクリック
        return _tone(1500, 0.18, 0.12, 30.0, (1.0,))
    if name == "ichimoku":     # 一目置いた：余韻の長い鈴
        return _mix(_tone(1760, 2.4, 0.18, 1.6, (1.0, 0.5, 0.2, 0.1)), _delay(_tone(2637, 2.0, 0.08, 1.8, (1.0,)), 0.05))
    if name == "mochikoshi":   # 持ち越し：低い二音
        return _mix(_tone(330, 1.6, 0.22, 2.2), _delay(_tone(262, 2.0, 0.22, 1.8), 0.35))
    if name == "logo":         # 番組ロゴ：やわらかい和音
        return _mix(_tone(523.25, 2.2, 0.14, 1.5), _tone(659.25, 2.2, 0.12, 1.5), _tone(783.99, 2.2, 0.1, 1.5))
    raise KeyError(name)
