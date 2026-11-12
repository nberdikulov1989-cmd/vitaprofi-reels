#!/usr/bin/env python3
"""Generate an original, royalty-free upbeat background track as a WAV file.

Pure numpy synthesis (no samples, no third-party audio), so there are no
copyright issues. The seed picks key, tempo and progression so videos vary
from day to day while staying in the same bright, positive style.

Usage: python3 tools/make_music.py <seconds> <out.wav> [seed]
"""
import sys
import wave

import numpy as np

SR = 44100

PROGRESSIONS = [  # scale degrees (0-based) of the chord roots, major key
    [0, 4, 5, 3],   # I V vi IV
    [0, 5, 3, 4],   # I vi IV V
    [5, 3, 0, 4],   # vi IV I V
    [0, 3, 4, 3],   # I IV V IV
]
MAJOR = [0, 2, 4, 5, 7, 9, 11]
KEYS = [60, 62, 64, 65, 67]  # C D E F G (MIDI root of the key, middle octave)


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env(n, a=0.005, r=0.25):
    t = np.arange(n) / SR
    e = np.minimum(1.0, t / a) * np.exp(-t / r)
    return e


def chord_notes(key, degree):
    return [key + MAJOR[(degree + k) % 7] + 12 * ((degree + k) // 7) for k in (0, 2, 4)]


def add(buf, start, sig):
    i = int(start * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i]


def pluck(f, dur, bright=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = (np.sin(2 * np.pi * f * t) + 0.35 * bright * np.sin(4 * np.pi * f * t)
         + 0.12 * bright * np.sin(6 * np.pi * f * t))
    return s * env(n, 0.004, 0.18)


def pad(fs, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.zeros(n)
    for f in fs:
        for det in (-0.12, 0.0, 0.12):  # light chorus
            s += np.sin(2 * np.pi * (f * (1 + det / 100)) * t)
    a = np.minimum(1.0, t / 0.35) * np.minimum(1.0, (dur - t) / 0.35)
    return s * a / (3 * len(fs))


def kick(dur=0.35):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 50 + 90 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)


def hat(rng, dur=0.06):
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    noise = np.diff(noise, prepend=0)  # crude high-pass
    return noise * np.exp(-np.arange(n) / SR * 70)


def clap(rng, dur=0.18):
    n = int(dur * SR)
    noise = np.diff(rng.standard_normal(n), prepend=0)
    return noise * np.exp(-np.arange(n) / SR * 22)


def bass(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)
    return s * env(n, 0.01, 0.35)


def generate(seconds, seed=0):
    rng = np.random.default_rng(seed)
    bpm = int(rng.choice([104, 108, 112, 116]))
    key = int(rng.choice(KEYS))
    prog = PROGRESSIONS[int(rng.integers(len(PROGRESSIONS)))]
    arp_pat = [[0, 1, 2, 1], [0, 2, 1, 2], [0, 1, 2, 3]][int(rng.integers(3))]
    beat = 60.0 / bpm
    bar = 4 * beat
    total = seconds + 1.0
    L = np.zeros(int(total * SR) + SR)
    R = np.zeros_like(L)

    nbars = int(np.ceil(total / bar))
    for b in range(nbars):
        t0 = b * bar
        deg = prog[b % len(prog)]
        notes = chord_notes(key, deg)
        p = pad([hz(m - 12) for m in notes], bar) * 0.22
        add(L, t0, p)
        add(R, t0, p)
        # bass: root on 1 and 3, octave pop on the "and" of 4
        root = hz(notes[0] - 24)
        for k, (pos, f) in enumerate([(0, root), (2, root), (3.5, root * 2)]):
            s = bass(f, beat * (0.9 if k < 2 else 0.45)) * 0.32
            add(L, t0 + pos * beat, s)
            add(R, t0 + pos * beat, s)
        # arpeggio in 8ths, panned slightly
        arp_notes = notes + [notes[0] + 12]
        for i in range(8):
            m = arp_notes[arp_pat[i % 4]] + (12 if i >= 4 and b % 2 else 0)
            s = pluck(hz(m), beat * 0.6) * 0.16
            pan = 0.35 if i % 2 else -0.35
            add(L, t0 + i * beat / 2, s * (1 - pan) / 1.35)
            add(R, t0 + i * beat / 2, s * (1 + pan) / 1.35)
        # drums: drop them in bar 0 for a soft intro
        if b > 0:
            for q in range(4):
                add(L, t0 + q * beat, kick() * 0.5)
                add(R, t0 + q * beat, kick() * 0.5)
            for q in (1, 3):
                c = clap(rng) * 0.10
                add(L, t0 + q * beat, c)
                add(R, t0 + q * beat, c)
            for e in range(8):
                h = hat(rng) * (0.05 if e % 2 else 0.03)
                add(L, t0 + e * beat / 2, h * 0.8)
                add(R, t0 + e * beat / 2, h * 1.2)

    n = int(seconds * SR)
    out = np.stack([L[:n], R[:n]], axis=1)
    # fades
    fi, fo = int(0.4 * SR), int(1.2 * SR)
    out[:fi] *= np.linspace(0, 1, fi)[:, None]
    out[-fo:] *= np.linspace(1, 0, fo)[:, None]
    # gentle soft-clip + normalize to about -14 dBFS peak-ish background level
    out = np.tanh(out * 1.4)
    out *= 0.6 / max(1e-9, np.max(np.abs(out)))
    return out, {"bpm": bpm, "key": key, "progression": prog}


def write_wav(path, data):
    pcm = (np.clip(data, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    secs = float(sys.argv[1])
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    data, info = generate(secs, seed)
    write_wav(sys.argv[2], data)
    print(info)
