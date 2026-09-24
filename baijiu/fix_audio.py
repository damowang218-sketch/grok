# -*- coding: utf-8 -*-
"""音频修复：按正确时间轴重排 EV + 台词变速 + BGM 重排(52s) + 重拼成片 v2
镜头真实时间轴: S1 0-3 | S2 3-6 | S3 6-8 | S4 8-10 | S5 10-12 | S6 12-15 | S7 15-17
                S8 17-20 | S9 20-23 | S10 23-26 | S11 26-29 | S12 29-33 | S13 33-36 | S14 36-39 | 片尾 39-52
"""
import numpy as np, wave, os, subprocess
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
BASE = '/home/user/grok/baijiu'
SFX, TTS, B, OUT = BASE+'/audio/sfx', BASE+'/audio/tts_clean', BASE+'/build', BASE+'/output'
SR = 44100
TOTAL = 52.0

def load(p):
    with wave.open(p) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float64)/32768
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(1)
    if sr != SR:
        x = np.interp(np.linspace(0, len(x)-1, int(round(len(x)*SR/sr))), np.arange(len(x)), x)
    return x

def save_wav(p, x):
    with wave.open(p, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1)*32767).astype('<i2').tobytes())

def atempo(src, dst, tempo):
    if os.path.exists(dst):
        return
    r = subprocess.run([FF, '-y', '-loglevel', 'error', '-i', src,
                        '-filter:a', 'atempo=%s' % tempo, '-ar', str(SR), dst],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    print('atempo %.2f -> %s (%.2fs)' % (tempo, os.path.basename(dst), len(load(dst))/SR))

os.makedirs(B+'/lines', exist_ok=True)
L = {}
for key, f, tp in [('l02', 'l02_xuxian.wav', 1.0), ('l03', 'l03_bai.wav', 1.28),
                   ('l04', 'l04_xiaoqing.wav', 1.0), ('l06', 'l06_bai.wav', 1.30),
                   ('l10', 'l10_bai_snake.wav', 1.20), ('l11', 'l11_xuxian.wav', 1.0),
                   ('l12', 'l12_vo.wav', 1.0), ('l13', 'l13_bai.wav', 1.22),
                   ('l14', 'l14_announcer.wav', 1.0), ('giggle', 'giggle.wav', 1.0)]:
    d = B+'/lines/%s.wav' % key
    atempo(TTS+'/'+f, d, tp)
    L[key] = d

# l03 尾部压低（让位给小青脚步/喊声）
x = load(L['l03'])
n1, n2 = int(1.8*SR), int(2.2*SR)
env = np.ones(len(x))
env[n1:n2] = np.linspace(1, 0.5, n2-n1)
env[n2:] = 0.5
L['l03'] = B+'/lines/l03_ducked.wav'; save_wav(L['l03'], x*env)
# l04 主/回音：在 10.42s 戛然而止（放置点 8.85 → 最长 1.57s，尾部的快淡出）
cut = int(1.57*SR)
x = load(L['l04'])[:cut]
x[-int(0.06*SR):] *= np.linspace(1, 0, int(0.06*SR))
save_wav(B+'/lines/l04_cut.wav', x)
xe = load(L['l04'])[:int(1.30*SR)]
xe[-int(0.06*SR):] *= np.linspace(1, 0, int(0.06*SR))
save_wav(B+'/lines/l04_echo.wav', xe)
print('line prep done')

# ---------------- BGM 52s 重排 ----------------
rng = np.random.default_rng(7)
def tt(dur): return np.arange(int(SR*dur))/SR
def env_ar(n, a=0.01, r=0.05):
    e = np.ones(n); na, nr = min(int(a*SR), n), min(int(r*SR), n)
    if na > 0: e[:na] *= np.linspace(0, 1, na)
    if nr > 0: e[-nr:] *= np.linspace(1, 0, nr)
    return e
def lp_s(x, a):
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc += a*(x[i]-acc); y[i] = acc
    return y
NOTE = dict(A2=110.0, B3=246.94, D3=146.83, A3=220.0, D4=293.66, E4=329.63, Fs4=369.99,
            A4=440.0, B4=493.88, D5=587.33, E5=659.26)
def pluck(freq, dur, amp=0.5, loss=0.996, bright=0.7):
    N = max(2, int(SR/freq))
    buf = rng.uniform(-1, 1, N)
    buf = np.convolve(buf, [0.6, 0.4], 'same')*(0.4+bright)
    n = int(SR*dur); out = np.empty(n); idx = 0
    for i in range(n):
        out[i] = buf[idx]; nxt = idx+1
        if nxt >= N: nxt = 0
        buf[idx] = loss*0.5*(buf[idx]+buf[nxt]); idx = nxt
    return out*env_ar(n, 0.002, min(0.09, dur*0.3))*amp
def flute(freq, dur, amp=0.35, vib=0.006, breath=0.05):
    t = tt(dur)
    f = freq*(1+vib*np.sin(2*np.pi*5.2*t)*np.minimum(1.0, t/0.5))
    ph = 2*np.pi*np.cumsum(f)/SR
    x = np.sin(ph)+0.30*np.sin(2*ph)+0.10*np.sin(3*ph)
    x += lp_s(rng.uniform(-1, 1, len(t)), 0.12)*breath*3
    return x*env_ar(len(t), min(0.14, dur*0.3), min(0.28, dur*0.4))*amp
def saw_drone(freq, dur, amp=0.1, nh=6):
    t = tt(dur); x = np.zeros(len(t))
    for k in range(1, nh+1):
        x += np.sin(2*np.pi*freq*k*t+rng.uniform(0, 6.28))/k
    return x*(1+0.15*np.sin(2*np.pi*0.9*t))*amp*env_ar(len(t), 0.3, 0.3)
def tremolo(freq, dur, amp=0.12, rate=14.0):
    t = tt(dur)
    return np.sin(2*np.pi*freq*t)*(0.5+0.5*np.sin(2*np.pi*rate*t))*np.minimum(1, t*2)**2*amp*env_ar(len(t), 0.05, 0.1)
def pad_chord(freqs, dur, amp=0.18):
    t = tt(dur); x = np.zeros(len(t))
    for f in freqs:
        x += np.sin(2*np.pi*f*t)+0.3*np.sin(4*np.pi*f*t)
    return x/len(freqs)*amp*env_ar(len(t), min(1.2, dur*0.3), min(1.5, dur*0.35))

buf = np.zeros(int(SR*TOTAL))
def add(x, at):
    st = int(at*SR); en = min(len(buf), st+len(x))
    if st < len(buf):
        buf[st:en] += x[:en-st]
def seq7(at, amp):
    s = [('D5', 0), ('A4', 0.115), ('D5', 0.23), ('E5', 0.345), ('D5', 0.46), ('B4', 0.69), ('A4', 0.805)]
    for nm, off in s:
        add(pluck(NOTE[nm], 0.12, amp=amp, loss=0.993), at+off)

# A 段 0-7.6 古风箫声+拨弦
arp = ['D4', 'Fs4', 'A4', 'B4', 'D5', 'B4', 'A4', 'Fs4']
for rep in range(2):
    for i, nm in enumerate(arp):
        add(pluck(NOTE[nm], 0.9, amp=0.30 if rep == 0 else 0.24), rep*4.0+0.05+i*0.5)
for at, nm, d_, a_ in [(0.5, 'A4', 1.1, 0.30), (1.7, 'B4', 0.6, 0.26), (2.35, 'D5', 1.2, 0.30),
                       (4.2, 'E5', 0.8, 0.24), (5.05, 'D5', 1.0, 0.26), (6.1, 'B4', 0.9, 0.22), (7.05, 'A4', 0.95, 0.24)]:
    add(flute(NOTE[nm], d_, amp=a_), at)
# B 段 7.6-10.4 紧张铺垫（小青狂奔）→ 10.4 急停
add(saw_drone(NOTE['A2'], 2.9, amp=0.11), 7.6)
pos = 7.95
gi = 0
while pos < 10.35:
    add(pluck(NOTE['A3' if int((pos*8)) % 2 == 0 else 'B3'], 0.14, amp=0.05+0.02*gi, loss=0.99), pos)
    pos += 0.125
    gi = min(gi+0.02, 6)
# 10.4-12.1 静默（roomtone only）
# C 段 12.1-15.7 低频紧张（晕眩）
add(saw_drone(NOTE['A2'], 3.6, amp=0.07), 12.1)
add(tremolo(NOTE['E4'], 2.1, amp=0.10, rate=11.0), 13.5)
# 15.7-17 倒下静场
# D 段 17.3-20 变身后 温暖稀疏拨弦
for at, nm in [(17.35, 'D4'), (18.15, 'A4'), (18.95, 'B4'), (19.55, 'D5')]:
    add(pluck(NOTE[nm], 0.7, amp=0.16, loss=0.994), at)
# 20-26 静音（S9/S10 喜剧留白）
# E 段 26.05-33 轻快鼓点+拨弦（许仙亮手机）
at = 26.05
while at < 32.9:
    seq7(at, 0.16)
    for kb in (0, 0.46):
        st = int((at+kb)*SR); d = int(0.1*SR); t2 = np.arange(d)/SR
        buf[st:st+d] += np.sin(2*np.pi*95*t2)*np.exp(-t2*35)*0.30
    at += 0.92
# 尾句 33-36
for at_, nm in [(33.1, 'D5'), (33.8, 'A4'), (34.7, 'E5'), (35.3, 'D5'), (35.75, 'B4')]:
    add(pluck(NOTE[nm], 0.15, amp=0.13, loss=0.993), at_)
# F 段 36-39.5 产品镜 和弦+上行琶音
add(pad_chord([NOTE['D3'], NOTE['A3'], NOTE['D4'], NOTE['Fs4']], 3.4, amp=0.20), 36.0)
for i, nm in enumerate(['D4', 'Fs4', 'A4', 'D5']):
    add(pluck(NOTE[nm], 0.8, amp=0.2), 36.15+i*0.18)
# G 段 39.5-50 片尾板 暖垫+稀疏琶音
add(pad_chord([NOTE['D3'], NOTE['A3'], NOTE['D4'], NOTE['Fs4']], 9.5, amp=0.16), 39.9)
for i, nm in enumerate(['D4', 'A4', 'Fs4', 'B4', 'D5', 'A4']):
    add(pluck(NOTE[nm], 0.9, amp=0.13, loss=0.994), 40.3+i*1.1)
add(flute(NOTE['E5'], 2.4, amp=0.14), 44.6)
add(flute(NOTE['D5'], 2.6, amp=0.16), 47.2)
# 全局尾部淡出 50.3-52
buf[int(50.3*SR):] *= np.linspace(1, 0, len(buf)-int(50.3*SR))**1.4
save_wav(SFX+'/bgm52.wav', buf*0.95)
print('bgm52 done %.1fs' % (len(buf)/SR))

# ---------------- 混音 v2 ----------------
mix = np.zeros(int(SR*TOTAL))
duckmask = np.ones(len(mix))
EV = [
    ('sfx', 'click.wav',        3.00, 0.40, 0),
    ('line', 'l02',             3.25, 1.00, 0.40),
    ('line', 'l03',             6.20, 1.00, 0.40),
    ('sfx', 'steps.wav',        8.05, 0.50, 0),
    ('line', 'l04_cut',         8.85, 1.00, 0.45),
    ('line', 'l04_echo',        9.50, 0.30, 0),
    ('sfx', 'gulp.wav',        10.48, 0.50, 0),
    ('sfx', 'rumble.wav',      12.15, 0.42, 0),
    ('line', 'l06',            12.50, 1.00, 0.40),
    ('sfx', 'spin.wav',        13.90, 0.45, 0),
    ('sfx', 'thud.wav',        15.95, 0.60, 0),
    ('sfx', 'shimmer.wav',     17.35, 0.60, 0),
    ('sfx', 'crickets.wav',    17.60, 0.45, 0),
    ('sfx', 'cicada.wav',      18.40, 0.45, 0),
    ('sfx', 'ding.wav',        20.55, 0.50, 0),
    ('sfx', 'boing.wav',       23.10, 0.55, 0),
    ('line', 'l10',            23.30, 1.00, 0.40),
    ('sfx', 'crow.wav',        23.85, 0.50, 0),
    ('sfx', 'drums_light.wav', 26.10, 0.55, 0),
    ('line', 'l11',            26.40, 1.00, 0.40),
    ('sfx', 'chime.wav',       29.15, 0.60, 0),
    ('line', 'l12',            29.50, 1.00, 0.40),
    ('sfx', 'slap.wav',        33.35, 0.50, 0),
    ('line', 'giggle',         33.70, 0.45, 0),
    ('line', 'l13',            33.90, 1.00, 0.40),
    ('line', 'l14',            39.80, 1.00, 0.40),
    ('sfx', 'chime.wav',       50.20, 0.40, 0),
]
def put(x, at, g=1.0):
    st = int(at*SR); en = min(len(mix), st+len(x))
    if st < len(mix):
        mix[st:en] += x[:en-st]*g
for kind, nm, at, g, dk in EV:
    if dk > 0:
        st = int(at*SR); en = min(len(mix), st+int(5.0*SR))
        d = np.ones(en-st); r = int(0.12*SR)
        d[:r] = np.linspace(1, 1-dk, r); d[-r:] = np.linspace(1-dk, 1, r); d[r:-r] = 1-dk
        duckmask[st:en] = np.minimum(duckmask[st:en], d)
def fit(x):
    return np.concatenate([x, np.zeros(len(mix)-len(x))]) if len(x) < len(mix) else x[:len(mix)]
put(fit(load(SFX+'/bgm52.wav'))*duckmask, 0.0, 0.88)
put(fit(load(SFX+'/roomtone.wav'))*duckmask, 0.0, 0.22)
for kind, nm, at, g, dk in EV:
    x = load(B+'/lines/%s.wav' % nm if kind == 'line' else SFX+'/'+nm)
    if kind == 'line' and nm != 'l04_echo':
        r = float(np.sqrt((x**2).mean())) or 1e-6
        g *= float(np.clip(0.115/r, 0.6, 2.4))
        print('gain %-8s x%.2f (rms %.3f)' % (nm, g, r))
    if nm == 'l04_echo':
        y = np.empty_like(x); acc = 0.0
        for i in range(len(x)):
            acc += 0.22*(x[i]-acc); y[i] = acc
        x = y
    put(x, at, g)
peak = np.max(np.abs(mix))
if peak > 0.97:
    mix *= 0.97/peak
save_wav(B+'/premix.wav', mix)
print('premix v2 ok peak %.2f' % peak)

# ---------------- 重拼成片 ----------------
r = subprocess.run([FF, '-y', '-hide_banner', '-loglevel', 'error',
                    '-f', 'concat', '-safe', '0', '-i', B+'/list.txt',
                    '-i', B+'/premix.wav',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    '-movflags', '+faststart', '-shortest', OUT+'/白蛇酒变_v2.mp4'],
                   capture_output=True, text=True)
print(r.stderr[-500:] if r.returncode else 'V2 RENDER OK %d KB' % (os.path.getsize(OUT+'/白蛇酒变_v2.mp4')//1024))
