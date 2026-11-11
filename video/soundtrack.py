#!/usr/bin/env python3
"""Space Janitor soundtrack: 90.0 s, stereo, 48 kHz, 16-bit. Pure numpy synthesis.

Regenerate:  /usr/bin/python3 video/soundtrack.py   (writes out/audio/soundtrack.wav)
"""
import os, wave
import numpy as np

SR = 48000
DUR = 90.0
N = int(SR * DUR)
STEP = 0.15            # one 16th at 100 BPM
BAR = 2.4
rng = np.random.default_rng(7)
TAU = 2 * np.pi

bed = np.zeros((N, 2))
arp = np.zeros((N, 2))   # plucks, gets a soft echo, then joins the bed
sfx = np.zeros((N, 2))


def db(x):
    return 10 ** (x / 20)


def mtof(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def fade(x, ms=10.0):
    n = min(int(SR * ms / 1000), len(x) // 2)
    if n > 0:
        w = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, n))
        x = x.copy()
        if x.ndim == 2:
            w = w[:, None]
        x[:n] *= w
        x[-n:] *= w[::-1]
    return x


def place(buf, t, sig, gain=1.0, pan=0.0):
    sig = fade(sig)
    i = int(round(t * SR))
    if i >= N:
        return
    sig = sig[: N - i]
    if sig.ndim == 1:
        a = (pan + 1) * np.pi / 4
        sig = np.stack([sig * np.cos(a), sig * np.sin(a)], axis=1) * np.sqrt(2) * 0.7071
    buf[i:i + len(sig)] += sig * gain


def place_sfx(t, sig, peak_db, pan=0.0):
    sig = sig / (np.max(np.abs(sig)) + 1e-12)
    place(sfx, t, sig, db(peak_db) / 0.7071 if sig.ndim == 1 and pan == 0 else db(peak_db), pan)


def tt(dur):
    return np.arange(int(SR * dur)) / SR


def bandnoise(dur, lo, hi):
    n = int(SR * dur)
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    mask = 1 / (1 + (lo / np.maximum(f, 1)) ** 6) / (1 + (f / hi) ** 6)
    x = np.fft.irfft(spec * mask, n)
    return x / (np.max(np.abs(x)) + 1e-12)


# ---------- instruments ----------
def pluck(m, dur=0.5, bright=0.6, decay=7.0):
    t = tt(dur)
    f = mtof(m)
    s = np.zeros_like(t)
    for n in range(1, 7):
        if n * f > 9000:
            break
        s += bright ** (n - 1) / n * np.sin(TAU * n * f * t) * np.exp(-t * decay * (0.6 + 0.4 * n))
    return s


def pad(m, dur):
    t = tt(dur)
    f = mtof(m)
    env = np.minimum(t / 0.5, 1) * np.minimum((dur - t) / 0.6, 1)
    out = []
    for det in (0.9985, 1.0015):
        ff = f * det
        out.append((np.sin(TAU * ff * t) + 0.25 * np.sin(TAU * 2 * ff * t + 0.5)
                    + 0.08 * np.sin(TAU * 3 * ff * t)) * env)
    return np.stack(out, axis=1)


def kick():
    t = tt(0.22)
    ph = TAU * np.cumsum(48 + 70 * np.exp(-t * 40)) / SR
    return np.sin(ph) * np.exp(-t * 16)


def hat(dur=0.06):
    return bandnoise(dur, 7000, 12000) * np.exp(-tt(dur) * 70)


def clap():
    t = tt(0.12)
    return bandnoise(0.12, 1200, 4500) * np.exp(-t * 35)


def bass(m, dur=0.28):
    t = tt(dur)
    f = mtof(m)
    return (np.sin(TAU * f * t) + 0.35 * np.sin(TAU * 2 * f * t) + 0.12 * np.sin(TAU * 3 * f * t)) * np.exp(-t * 5)


def bell(f, dur=1.3):
    t = tt(dur)
    s = np.zeros_like(t)
    for r, a, d in ((1, 1, 3.5), (2.76, 0.45, 6), (5.4, 0.2, 10), (2.0, 0.3, 4.5)):
        s += a * np.sin(TAU * f * r * t) * np.exp(-t * d)
    return s


def tink():
    f = rng.uniform(1900, 3200)
    t = tt(0.35)
    s = np.zeros_like(t)
    for r, a in ((1, 1), (1.47, 0.6), (2.09, 0.4), (2.9, 0.25)):
        s += a * np.sin(TAU * f * r * t + rng.uniform(0, TAU)) * np.exp(-t * (14 + 6 * r))
    return s


def hum(dur, f0=55.0, f1=220.0):
    t = tt(dur)
    x = t / dur
    ph = TAU * np.cumsum(f0 * (f1 / f0) ** (x ** 1.3)) / SR
    s = sum(np.sin(n * ph) / n for n in range(1, 6)) + 0.25 * np.sin(8 * ph) * x
    trem = 1 - 0.3 * (0.5 + 0.5 * np.sin(TAU * np.cumsum(4 + 16 * x) / SR))
    return s * trem * (0.08 + 0.92 * x ** 1.4)


def whoosh(dur, lo=300, hi=5000):
    t = tt(dur)
    x = t / dur
    out = np.zeros_like(t)
    cs = np.geomspace(lo, hi, 5)
    for i, c in enumerate(cs):
        out += bandnoise(dur, c * 0.7, c * 1.4) * np.exp(-((x - (0.15 + 0.7 * i / 4)) / 0.22) ** 2)
    return out * np.sin(np.pi * x) ** 1.5


def pop():
    t = tt(0.9)
    ph = TAU * np.cumsum(180 + 1500 * np.minimum(t / 0.05, 1) ** 2 * np.exp(-t * 6)) / SR
    body = np.sin(ph) * np.exp(-t * 22)
    burst = bandnoise(0.9, 800, 9000) * np.exp(-t * 9) * 0.6
    low = np.sin(TAU * 70 * t) * np.exp(-t * 14) * 0.7
    return body + burst + low


def sparkle(dur=1.4, count=14):
    out = np.zeros(int(SR * dur))
    for _ in range(count):
        t0 = rng.uniform(0, dur - 0.3) ** 1.0
        f = rng.choice([2093, 2637, 3136, 3951, 4186, 5274])
        t = tt(0.25)
        g = np.sin(TAU * f * t) * np.exp(-t * 22) * (1 - t0 / dur)
        i = int(t0 * SR)
        out[i:i + len(g)] += fade(g, 3)
    return out


def whistle(f, dur, vib=0.012, glide_from=None):
    t = tt(dur)
    fr = np.full_like(t, f)
    if glide_from:
        fr = f + (glide_from - f) * np.exp(-t * 30)
    fr = fr * (1 + vib * np.sin(TAU * 5.5 * t) * np.minimum(t / 0.15, 1))
    ph = TAU * np.cumsum(fr) / SR
    env = np.minimum(t / 0.04, 1) * np.minimum((dur - t) / 0.08, 1)
    return (np.sin(ph) + 0.08 * np.sin(2 * ph) + 0.04 * bandnoise(dur, 2000, 6000)) * env


# ---------- harmony ----------
CH = {  # bass root (midi), triad voicing
    'C': (36, (60, 64, 67)), 'Am': (33, (57, 60, 64)), 'F': (29 + 12, (57, 60, 65)),
    'G': (31 + 12, (59, 62, 67)), 'Dm': (38, (57, 62, 65)),
}
LEAD = {
    'C': (67, 72, 76, 79, 76, None, 72, None), 'F': (69, 72, 77, 81, 77, None, 72, None),
    'Am': (69, 72, 76, 81, 76, None, 72, None), 'G': (67, 71, 74, 79, 74, None, 71, 74),
    'Gend': (67, 71, 74, 79, 77, None, 74, 71),
}


def arp_note(ch, i):
    a, b, c = CH[ch][1]
    return (a, c, a + 12, b + 12, c, a + 12, b, c)[i % 8]


def chord_pad(t, ch, dur, g):
    root, tri = CH[ch]
    for m in tri:
        place(bed, t, pad(m, dur), g * 0.16)
    place(bed, t, pad(root + 12, dur), g * 0.14)


def bar_t(b):
    return b * BAR


def groove(b, ch, g=1.0, kick_on=True, hats=True, claps=False, bass_on=True, arp_on=True,
           pad_on=True, lead=None, t_from=0.0, t_to=1e9, arp_steps=range(8)):
    """One bar on an 8th-note grid (0.3 s). Events outside [t_from, t_to) are skipped."""
    t0 = bar_t(b)
    root = CH[ch][0]
    if pad_on:
        s = max(t0, t_from)
        e = min(t0 + BAR, t_to)
        if e - s > 0.3:
            chord_pad(s, ch, e - s + 0.3, g)
    for i in range(8):
        t = t0 + i * 0.3
        if not (t_from <= t < t_to - 1e-6):
            continue
        if arp_on and i in arp_steps:
            place(arp, t, pluck(arp_note(ch, i)), g * 0.30 * (1.0 if i % 2 == 0 else 0.75),
                  pan=0.35 * (-1) ** i)
        if kick_on and i % 2 == 0:
            place(bed, t, kick(), g * 0.55)
        if hats and i % 2 == 1:
            place(bed, t, hat(), g * 0.10, pan=0.2)
        if claps and i in (2, 6):
            place(bed, t, clap(), g * 0.13, pan=-0.1)
        if bass_on and i in (0, 3, 4, 6):
            place(bed, t, bass(root + (12 if i == 3 else 0)), g * 0.34)
        if lead and lead[i] is not None:
            place(arp, t, pluck(lead[i] + 0, 0.7, bright=0.75, decay=5), g * 0.42, pan=0.0)


# ================= BED =================
# 0-3.5 Sun: low drone + slow swell (lingers quietly under the entry)
t = tt(9.0)
swell = np.minimum(t / 3.2, 1) ** 1.5 * np.interp(t, [0, 3.5, 5.0, 9.0], [1, 1, 0.45, 0.0])
dr = np.zeros((len(t), 2))
for f, a in ((32.7, 0.8), (65.4, 1.0), (98.0, 0.45), (130.8, 0.35), (196.0, 0.14), (261.6, 0.07)):
    for c, det in enumerate((0.998, 1.002)):
        dr[:, c] += a * np.sin(TAU * f * det * t + c) * (1 + 0.15 * np.sin(TAU * 0.21 * t + f))
place(bed, 0.0, dr * swell[:, None], 0.42)

# 3.6-8 Earth / rockets: beat + arpeggio enter
groove(1, 'C', 0.8, t_from=3.6)
groove(2, 'F', 0.8)
groove(3, 'C', 0.8, t_to=8.1)
# 8-17 junk drift: sparse, minor colour; 17-21.6 same, thinner
for b, ch in ((3, 'Am'), (4, 'Am'), (5, 'Dm'), (6, 'Am'), (7, 'Dm'), (8, 'Am')):
    late = b >= 7
    groove(b, ch, 0.55 if not late else 0.45, kick_on=False, hats=False, bass_on=False,
           arp_steps=(0, 3, 6) if not late else (0, 5), t_from=8.1 if b == 3 else 0,
           t_to=19.5 if b == 8 else 1e9)
    if b > 3:
        place(bed, bar_t(b), bass(CH[ch][0] + 12, 0.6), 0.2)
# 21.6-24 lift into the reveal (dominant swell, rising arp)
groove(9, 'G', 0.6, kick_on=False, hats=True, bass_on=False)
place(bed, 21.6, pad(79, 2.6) * np.linspace(0, 1, int(SR * 2.6))[:, None], 0.1)
# 24-30 hero theme
for b, ch in ((10, 'C'), (11, 'F'), (12, 'Am')):
    groove(b, ch, 1.0, claps=True, lead=LEAD[ch], t_to=30.0)
for m in (60, 64, 67, 72, 76):   # theme hit at 24.0
    place(arp, 24.0, pluck(m, 1.2, bright=0.85, decay=3), 0.13, pan=(m - 67) / 20)
# 30-37 swarm deploys: lighter, leaves room for blips
groove(12, 'Am', 0.75, t_from=30.0)
groove(13, 'G', 0.75)
groove(14, 'C', 0.75)
# 36-48 one continuous, calm stretch of the groove that gently builds anticipation.
# 37-41.2 beauty close-up of a mirror satellite (airy: no kick, high shimmer),
# 41.2-47 the whole swarm slowly turns toward the dead satellite (kick returns, level creeps up).
# This section draws its noise from its own generator and then advances the main one by the
# amount the earlier cut used, so every random detail elsewhere in the track stays identical.
_main_rng = rng
rng = np.random.default_rng(41)
groove(15, 'F', 0.7)
groove(16, 'Am', 0.60, kick_on=False)
groove(17, 'Dm', 0.62)
groove(18, 'G', 0.66)
groove(19, 'G', 0.70)
# shimmer: soft high pad + offbeat glassy arpeggio, 37.0-41.4
t = tt(4.4)
shim_env = (np.sin(np.pi * t / 4.4) ** 0.8 * (0.8 + 0.2 * np.sin(TAU * 3.1 * t)))[:, None]
for m, g_ in ((84, 0.050), (88, 0.040), (91, 0.035), (96, 0.022)):
    place(bed, 37.0, pad(m, 4.4) * shim_env, g_)
for k in range(14):
    tk = 37.05 + 0.3 * k
    tri = CH['F'][1] if tk < 38.4 else CH['Am'][1]
    m = (tri[0] + 24, tri[2] + 24, tri[1] + 36, tri[2] + 24, tri[0] + 36, tri[1] + 24)[k % 6]
    place(arp, tk, pluck(m, 0.7, bright=0.35, decay=5), 0.085 * np.sin(np.pi * (k + 1) / 15) ** 0.6 + 0.03,
          pan=0.6 * (-1) ** k)
rng = _main_rng
rng.standard_normal(11 * int(SR * 0.06))
# 48-54.5 building on the right target
groove(20, 'C', 0.55, kick_on=False, claps=False)
groove(21, 'F', 0.72)
groove(22, 'G', 0.9, claps=True, t_to=54.5)
# 55.2-60 afterglow: pad + sparse arp, resolves into 60
groove(23, 'F', 0.5, kick_on=False, hats=False, bass_on=False, arp_steps=(0, 2, 4, 6))
groove(24, 'G', 0.55, kick_on=False, hats=True, bass_on=False)
# 60-72 business: confident full groove
for b, ch in zip(range(25, 30), ('C', 'Am', 'F', 'G', 'C')):
    groove(b, ch, 1.0, claps=True)
# 72-79.2 villain: sneaky minor pizzicato tiptoe
VIL = ((48, None, 51, None, 55, None, 56, 55), (54, None, 51, None, 50, None, 47, None),
       (48, None, 51, None, 55, None, 56, 55))
for bi, line in enumerate(VIL):
    for i, m in enumerate(line):
        t0 = bar_t(30 + bi) + i * 0.3
        if m is not None:
            place(bed, t0, pluck(m, 0.22, bright=0.7, decay=13), 0.50)
            place(arp, t0, pluck(m + 12, 0.18, bright=0.5, decay=16), 0.14, pan=0.25)
        if i % 4 == 2:
            place(bed, t0, hat(0.05), 0.07, pan=-0.2)
# 84-90 final theme, resolve on the tonic
groove(35, 'F', 1.0, claps=True, lead=LEAD['F'])
groove(36, 'G', 1.0, claps=True, lead=LEAD['Gend'])
chord_pad(88.8, 'C', 1.2, 1.1)
place(bed, 88.8, kick(), 0.55)
place(bed, 88.8, bass(36, 1.2), 0.36)
for m in (60, 64, 67, 72, 84):
    place(arp, 88.8, pluck(m, 1.2, bright=0.8, decay=3), 0.14, pan=(m - 70) / 25)

# echo on plucks (dotted 8th, ping-pong), then fold into the bed
d = int(0.45 * SR)
echo = np.zeros_like(arp)
echo[d:] += 0.30 * arp[:-d, ::-1]
echo[2 * d:] += 0.12 * arp[:-2 * d]
bed += arp + echo

# bed automation: dip after the collision, duck around the vaporize pop, clear for the whistle
tl = np.arange(N) / SR
auto = np.interp(tl,
                 [0, 19.55, 19.62, 21.6, 54.49, 54.51, 55.2, 56.5,
                  79.2, 79.5, 83.95, 84.0, 90],
                 [1, 1.00, 0.45, 1.0, 1.00, 0.25, 0.25, 1.0,
                  1.0, 0.0, 0.0, 1.0, 1.0])
bed *= auto[:, None]

# ================= SFX =================
for t0 in (4.1, 5.5, 6.8):                       # rocket whooshes
    place_sfx(t0, whoosh(1.5, 250, 4000), -13, pan=rng.uniform(-0.5, 0.5))
for t0, p in ((9.3, -0.5), (11.8, 0.4), (13.1, -0.2), (15.4, 0.6), (16.2, -0.6), (18.0, 0.3)):
    place_sfx(t0, tink(), -13, pan=p)            # metallic tinks
# 19.6 collision: low thump + debris rattle
t = tt(0.7)
thump = np.sin(TAU * np.cumsum(38 + 90 * np.exp(-t * 25)) / SR) * np.exp(-t * 7) \
    + 0.5 * bandnoise(0.7, 80, 900) * np.exp(-t * 18) + 0.3 * np.sin(TAU * 150 * t) * np.exp(-t * 20)
place_sfx(19.6, thump, -4)
for k in range(16):
    dt = 0.08 + 1.9 * (k / 16) ** 1.6 + rng.uniform(0, 0.05)
    place_sfx(19.6 + dt, tink(), -10 - 0.7 * k, pan=rng.uniform(-0.8, 0.8))
# 30.3 swarm blips: 18, one per satellite
SCALE = (0, 2, 4, 7, 9)
for k in range(18):
    m = 72 + 12 * (k // 5) + SCALE[k % 5]
    t = tt(0.09)
    f = mtof(m)
    b = (np.sin(TAU * f * t) + 0.3 * np.sin(TAU * 2 * f * t)) * np.exp(-t * 18)
    place_sfx(30.3 + 0.11 * k, b, -11, pan=0.6 * (-1) ** k)
# 41.5-44 the swarm turns: subtle low servo swell
t = tt(2.5)
x = t / 2.5
ph = TAU * np.cumsum(62 + 48 * np.sin(np.pi * x / 2) ** 2) / SR
servo = sum(np.sin(n * ph) / n ** 1.2 for n in range(1, 7)) * (1 + 0.12 * np.sin(TAU * 23 * t))
place_sfx(41.5, servo * np.sin(np.pi * x) ** 1.5, -19)
# 44.5 soft "target lock" double-beep
for t0 in (44.5, 44.66):
    t = tt(0.09)
    beep = (np.sin(TAU * 1568 * t) + 0.2 * np.sin(TAU * 3136 * t)) \
        * np.minimum(t / 0.006, 1) * np.minimum((0.09 - t) / 0.03, 1)
    place_sfx(t0, beep, -12, pan=0.1)
rng.standard_normal(int(SR * 0.42))   # keeps later random details where they were
# 47 charge on the right target -> 54.5 vaporize
place_sfx(47.0, hum(7.5, 55, 262), -8)
place_sfx(54.5, pop(), -4)
place_sfx(54.45, whoosh(1.1, 800, 9000), -10)
place_sfx(54.55, sparkle(), -10, pan=0.2)
# 55.5-58.8 falling whistle + burn fizz, ding at 59.0
t = tt(3.3)
x = t / 3.3
fall = np.sin(TAU * np.cumsum(1700 * (330 / 1700) ** x * (1 + 0.01 * np.sin(TAU * 7 * t))) / SR) * (1 - 0.6 * x)
place_sfx(55.5, fall, -12, pan=-0.2)
fizz = bandnoise(4.0, 3500, 11000) * (0.4 + 0.6 * rng.random(int(SR * 4.0)) ** 6) * np.exp(-tt(4.0) * 0.8)
place_sfx(55.5, fizz, -17, pan=0.2)
place_sfx(59.0, bell(1318.5), -6)
# 79.4 charge -> 81.4 pop
place_sfx(79.4, hum(2.0, 70, 262), -8)
place_sfx(81.4, pop(), -4)
place_sfx(81.45, sparkle(0.9, 8), -12, pan=-0.2)
# 82-84 innocent whistle
for t0, f, d_, gl in ((82.1, 784.0, 0.5, 740), (82.7, 1046.5, 0.45, 990), (83.25, 880.0, 0.65, 932)):
    place_sfx(t0, whistle(f, d_, glide_from=gl), -12)

# ================= MASTER =================
# gentle soft-knee on the bed so stray transients don't set the level, then peak at -14 dBFS
ref = np.percentile(np.abs(bed[np.abs(bed) > 1e-4]), 99.5)
bed = np.tanh(bed / (1.6 * ref))
bed *= db(-14) / np.max(np.abs(bed))
pk = np.max(np.abs(sfx))
if pk > db(-4):
    sfx *= db(-4) / pk
mix = bed + sfx
pk = np.max(np.abs(mix))
if pk > db(-1.5):
    mix *= db(-1.5) / pk
nf = int(1.5 * SR)
mix[-nf:] *= (0.5 + 0.5 * np.cos(np.linspace(0, np.pi, nf)))[:, None]
mix[: int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))[:, None]
assert not np.isnan(mix).any()

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'audio', 'soundtrack.wav')
os.makedirs(os.path.dirname(out), exist_ok=True)
pcm = np.round(mix * 32767).astype('<i2')
with wave.open(out, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(pcm.tobytes())

# ================= CHECKS =================
def dbfs(x):
    return 20 * np.log10(max(float(x), 1e-9))

with wave.open(out, 'rb') as w:
    frames, sr, chn, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
    data = np.frombuffer(w.readframes(frames), dtype='<i2').reshape(-1, 2) / 32768.0
print(f'file: {os.path.normpath(out)}')
print(f'duration {frames / sr:.3f} s  rate {sr}  channels {chn}  bits {sw * 8}')
print(f'peak mix {dbfs(np.max(np.abs(data))):.2f} dBFS | bed bus {dbfs(np.max(np.abs(bed))):.2f} | sfx bus {dbfs(np.max(np.abs(sfx))):.2f}')
print(f'NaN: {bool(np.isnan(data).any())}  clipped samples: {int((np.abs(pcm) >= 32767).sum())}')
print('RMS per 5 s window (dBFS):')
for s in range(0, 90, 5):
    seg = data[s * SR:(s + 5) * SR]
    print(f'  {s:2d}-{s + 5:2d}s  {dbfs(np.sqrt(np.mean(seg ** 2))):6.1f}')
print('event energy (RMS dBFS over 0.25 s from the cue; peak):')
EV = [(1.5, 'sun drone'), (3.6, 'beat in'), (9.3, 'tink'), (19.6, 'collision'), (24.0, 'theme hit'),
      (30.3, 'first blip'), (32.17, 'last blip'), (38.0, 'shimmer'), (42.7, 'servo swell'),
      (44.5, 'target lock'), (46.0, 'groove'), (50.0, 'charge+build'),
      (54.5, 'vaporize'), (57.0, 'falling whistle'), (59.0, 'ding'), (60.0, 'groove'),
      (72.0, 'villain bass'), (80.5, 'charge'), (81.4, 'pop'), (82.1, 'whistle 1'), (82.7, 'whistle 2'),
      (83.25, 'whistle 3'), (84.0, 'final theme'), (88.8, 'tonic'), (89.9, '(end of fade)')]
for t0, name in EV:
    seg = data[int(t0 * SR):int((t0 + 0.25) * SR)]
    print(f'  {t0:6.2f}s {name:16s} rms {dbfs(np.sqrt(np.mean(seg ** 2))):6.1f}  peak {dbfs(np.max(np.abs(seg))):6.1f}')
