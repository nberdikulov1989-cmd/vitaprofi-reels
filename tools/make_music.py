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


STYLES = {
    # name: (bpm choices, swing, kick beats, offbeat bass, drum level)
    "pop":   ([104, 108, 112, 116], 0.0, (0, 1, 2, 3), False, 1.0),
    "house": ([118, 120, 122, 124], 0.0, (0, 1, 2, 3), True, 1.0),
    "lofi":  ([84, 88, 92], 0.18, (0, 2.5), False, 0.7),
    "funk":  ([96, 100, 104], 0.1, (0, 0.75, 2, 2.5), False, 0.9),
}


def generate(seconds, seed=0):
    rng = np.random.default_rng(seed)
    style = list(STYLES)[int(rng.integers(len(STYLES)))]
    bpms, swing, kicks, offbeat_bass, drum_lvl = STYLES[style]
    bpm = int(rng.choice(bpms))
    key = int(rng.choice(KEYS))
    prog = PROGRESSIONS[int(rng.integers(len(PROGRESSIONS)))]
    arp_pat = [[0, 1, 2, 1], [0, 2, 1, 2], [0, 1, 2, 3], [3, 2, 1, 0]][int(rng.integers(4))]
    bright = float(rng.uniform(0.3, 1.4))      # lead timbre
    arp_oct = int(rng.choice([0, 12]))          # lead register
    beat = 60.0 / bpm
    bar = 4 * beat
    total = seconds + 1.0
    L = np.zeros(int(total * SR) + SR)
    R = np.zeros_like(L)

    def eighth(i):  # time of the i-th 8th note within a bar, with swing
        return i * beat / 2 + (swing * beat / 2 if i % 2 else 0.0)

    nbars = int(np.ceil(total / bar))
    for b in range(nbars):
        t0 = b * bar
        deg = prog[b % len(prog)]
        notes = chord_notes(key, deg)
        p = pad([hz(m - 12) for m in notes], bar) * (0.28 if style == "lofi" else 0.22)
        add(L, t0, p)
        add(R, t0, p)
        root = hz(notes[0] - 24)
        if offbeat_bass:
            bass_hits = [(q + 0.5, root, 0.4) for q in range(4)]
        else:
            bass_hits = [(0, root, 0.9), (2, root, 0.9), (3.5, root * 2, 0.45)]
        for pos, f, ln in bass_hits:
            s = bass(f, beat * ln) * 0.32
            add(L, t0 + pos * beat, s)
            add(R, t0 + pos * beat, s)
        arp_notes = notes + [notes[0] + 12]
        for i in range(8):
            m = arp_notes[arp_pat[i % 4]] + arp_oct + (12 if i >= 4 and b % 2 and not arp_oct else 0)
            s = pluck(hz(m), beat * 0.6, bright) * 0.16
            pan = 0.35 if i % 2 else -0.35
            add(L, t0 + eighth(i), s * (1 - pan) / 1.35)
            add(R, t0 + eighth(i), s * (1 + pan) / 1.35)
        if b > 0:  # bar 0 is a soft intro without drums
            for q in kicks:
                add(L, t0 + q * beat, kick() * 0.5 * drum_lvl)
                add(R, t0 + q * beat, kick() * 0.5 * drum_lvl)
            for q in (1, 3):
                c = clap(rng) * 0.10 * drum_lvl
                add(L, t0 + q * beat, c)
                add(R, t0 + q * beat, c)
            for e in range(8):
                lvl = (0.06 if e % 2 else 0.02) if style == "house" else (0.05 if e % 2 else 0.03)
                h = hat(rng) * lvl * drum_lvl
                add(L, t0 + eighth(e), h * 0.8)
                add(R, t0 + eighth(e), h * 1.2)

    n = int(seconds * SR)
    out = np.stack([L[:n], R[:n]], axis=1)
    fi, fo = int(0.4 * SR), int(1.2 * SR)
    out[:fi] *= np.linspace(0, 1, fi)[:, None]
    out[-fo:] *= np.linspace(1, 0, fo)[:, None]
    out = np.tanh(out * 1.4)
    out *= 0.6 / max(1e-9, np.max(np.abs(out)))
    return out, {"style": style, "bpm": bpm, "key": key, "progression": prog}


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
