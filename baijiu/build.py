# -*- coding: utf-8 -*-
"""《白蛇酒变》别传 x 舒达AI DREAM —— 一键成片脚本
时间轴(秒): 3,3,2,2,2,3,2,3,3,3,3,4,3,3 = 39s  (+13s 片尾板 = 52s)
"""
import numpy as np, wave, os, subprocess, sys
import pymupdf
from PIL import Image, ImageDraw

BASE = '/home/user/grok/baijiu'
A, SFX, TTS, UI, B, OUT = (BASE+'/assets', BASE+'/audio/sfx', BASE+'/audio/tts_clean',
                           BASE+'/ui', BASE+'/build', BASE+'/output')
os.makedirs(UI, exist_ok=True); os.makedirs(B, exist_ok=True); os.makedirs(OUT, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
SR = 44100
FPS = 30
W, H = 1920, 1080

# ---------------- 时间轴 ----------------
SHOTS = [  # (素材名, 时长s, 运镜, 字幕png或None)
    ('shot01_empty',    3.0, ('zoom', 1.00, 1.085), 'title.png'),
    ('shot02_toast',    3.0, ('zoom', 1.001, 1.001), None),
    ('S03',             2.0, ('zoom', 1.00, 1.07), None),   # 替身
    ('shot04_xiaoqing', 2.0, ('zoom', 1.00, 1.10), None),
    ('S05',             2.0, ('zoomtilt', 1.00, 1.12, 0.05), None),  # 替身
    ('shot06_dizzy',    3.0, ('sway', 1.07, 8.0, 13.0), None),
    ('shot07_fall',     2.0, ('zoom', 1.00, 1.13), None),
    ('shot08_snake',    3.0, ('zoom', 1.10, 1.00), None),
    ('S09',             3.0, ('zoom', 1.03, 1.06), None),   # 替身
    ('S10',             3.0, ('zoom', 1.00, 1.12), None),   # 替身
    ('shot11_phone',    3.0, ('zoom', 1.001, 1.001), 'sub11.png'),
    ('shot12_appui',    4.0, ('zoom', 1.00, 1.06), 'sub12.png'),
    ('shot13_pat',      3.0, ('shake', 1.02), None),
    ('shot14_mattress', 3.0, ('zoom', 1.00, 1.09), 'sub14.png'),
]
SUB_FADE = {'title.png': (0.45, 0.45, 2.55, 0.45),
            'sub11.png': (0.30, 0.30, 2.60, 0.40),
            'sub12.png': (0.35, 0.35, 3.55, 0.45),
            'sub14.png': (0.40, 0.40, 2.50, 0.50)}
TOTAL_FILM = sum(s[1] for s in SHOTS)
ENDCARD_DUR = 13.0
TOTAL = TOTAL_FILM + ENDCARD_DUR

def src(name):
    p = os.path.join(A, name + '.png')
    if os.path.exists(p):
        return p
    return os.path.join(B, name + '.jpg')   # 替身

# ---------------- 替身裁切 ----------------
def make_standin(src_img, cx, cy, wfrac, out):
    im = Image.open(src_img).convert('RGB')
    W0, H0 = im.size
    cw = wfrac * W0
    ch = cw * 9 / 16
    x0 = min(max(cx * W0 - cw / 2, 0), W0 - cw)
    y0 = min(max(cy * H0 - ch / 2, 0), H0 - ch)
    im.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((1920, 1080), Image.LANCZOS).save(out, quality=92)
    print('standin', os.path.basename(out))

if not os.path.exists(B + '/S03.jpg'):
    make_standin(A + '/shot02_toast.png', 0.63, 0.34, 0.46, B + '/S03.jpg')     # 白娘子端杯(近)
    make_standin(A + '/shot02_toast.png', 0.60, 0.26, 0.27, B + '/S05.jpg')     # 举杯(特写)
    make_standin(A + '/shot02_toast.png', 0.24, 0.26, 0.38, B + '/S09.jpg')     # 许仙(中近)
    make_standin(A + '/shot08_snake.png', 0.53, 0.40, 0.30, B + '/S10.jpg')     # 小蛇(特写)

# 质检拼图 v2
names = [s[0] for s in SHOTS]
tw, th = 480, 270
sheet = Image.new('RGB', (tw * 4, th * 4 + 30), (18, 18, 22))
d = ImageDraw.Draw(sheet)
for i, nm in enumerate(names):
    p = src(nm)
    x, y = (i % 4) * tw, (i // 4) * th
    im = Image.open(p).convert('RGB')
    r = max(tw / im.width, th / im.height)
    im = im.resize((int(im.width * r) + 1, int(im.height * r) + 1))
    im = im.crop(((im.width - tw) // 2, (im.height - th) // 2, (im.width - tw) // 2 + tw, (im.height - th) // 2 + th))
    sheet.paste(im, (x, y))
    d.rectangle([x + 4, y + 4, x + 150, y + 26], fill=(0, 0, 0))
    d.text((x + 10, y + 8), nm[:14], fill=(255, 220, 80))
sheet.save(B + '/sheet_v2.jpg', quality=88)
print('sheet_v2 ok')

# ---------------- 字幕 PNG（幂等重画） ----------------
font = pymupdf.Font('china-s')
def render_sub(text, fontsize, cy, out):
    stroke = max(5, int(fontsize * 0.055))
    doc = pymupdf.open(); page = doc.new_page(width=1920, height=1080)
    w = font.text_length(text, fontsize=fontsize)
    x0 = (1920 - w) / 2
    twb = pymupdf.TextWriter(page.rect)
    for dx in (-stroke, 0, stroke):
        for dy in (-stroke, 0, stroke):
            if (dx, dy) != (0, 0):
                twb.append((x0 + dx, cy + dy), text, font=font, fontsize=fontsize)
    twb.write_text(page, color=(0, 0, 0))
    tw = pymupdf.TextWriter(page.rect)
    tw.append((x0, cy), text, font=font, fontsize=fontsize)
    tw.write_text(page, color=(1, 1, 1))
    page.get_pixmap(alpha=True).save(out)
render_sub('《白蛇酒变》别传', 130, 430, UI + '/title.png')
render_sub('早就知道？！', 92, 962, UI + '/sub11.png')
render_sub('压力感知成像', 92, 962, UI + '/sub12.png')
render_sub('超精感知，睡姿识别', 92, 962, UI + '/sub14.png')
# 片尾板
doc = pymupdf.open(); page = doc.new_page(width=1920, height=1080)
page.draw_rect(page.rect, color=(0, 0, 0), fill=(0, 0, 0), fill_opacity=0.52)
for txt, fs, cy in [('舒达AI DREAM · 智适应床垫X1', 86, 470), ('超精感知 · 睡姿识别', 52, 600)]:
    w = font.text_length(txt, fontsize=fs); x0 = (1920 - w) / 2
    twb = pymupdf.TextWriter(page.rect)
    for dx in (-4, 0, 4):
        for dy in (-4, 0, 4):
            if (dx, dy) != (0, 0):
                twb.append((x0 + dx, cy + dy), txt, font=font, fontsize=fs)
    twb.write_text(page, color=(0, 0, 0))
    tw = pymupdf.TextWriter(page.rect)
    tw.append((x0, cy), txt, font=font, fontsize=fs)
    tw.write_text(page, color=(1, 1, 1))
page.get_pixmap(alpha=True).save(UI + '/endcard.png')
print('subs + endcard ok')

# ---------------- 混音 ----------------
def load(p):
    with wave.open(p) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), '<i2').astype(np.float64) / 32768
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(1)
    if sr != SR:
        n = int(round(len(x) * SR / sr))
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)
    return x

def lp(x, a):
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc += a * (x[i] - acc); y[i] = acc
    return y

mix = np.zeros(int(SR * TOTAL))
duckmask = np.ones(len(mix))
def put(x, at, g=1.0):
    st = int(at * SR); en = min(len(mix), st + len(x))
    if st >= len(mix):
        return
    mix[st:en] += x[:en - st] * g

B0 = BASE + '/audio/sfx'
EV = [
    ('click.wav',             3.00, 0.50, 0),
    ('tts:l02_xuxian.wav',    3.25, 1.00, 0.40),
    ('tts:l03_bai.wav',       6.30, 1.00, 0.40),
    ('tts:giggle.wav',       10.60, 0.50, 0),
    ('steps.wav',            11.00, 0.50, 0),
    ('tts:l04_xiaoqing.wav', 11.90, 1.00, 0.45),
    ('tts:l04_xiaoqing.wav', 12.55, 0.40, 0),
    ('shimmer.wav',          15.55, 0.75, 0),
    ('cicada.wav',           16.55, 0.60, 0),
    ('gulp.wav',             20.05, 0.80, 0),
    ('rumble.wav',           21.30, 0.50, 0),
    ('tts:l06_bai.wav',      21.70, 1.00, 0.40),
    ('spin.wav',             22.90, 0.45, 0),
    ('thud.wav',             26.00, 0.75, 0),
    ('shimmer.wav',          26.45, 0.85, 0),
    ('crickets.wav',         26.60, 0.50, 0),
    ('ding.wav',             29.00, 0.50, 0),
    ('boing.wav',            29.80, 0.55, 0),
    ('crow.wav',             30.60, 0.50, 0),
    ('drums_light.wav',      33.05, 0.60, 0),
    ('tts:l11_xuxian.wav',   33.30, 1.00, 0.40),
    ('chime.wav',            36.05, 0.60, 0),
    ('tts:l12_vo.wav',       36.30, 1.00, 0.40),
    ('slap.wav',             39.55, 0.65, 0),
    ('tts:giggle.wav',       40.05, 0.45, 0),
    ('tts:l13_bai.wav',      40.45, 1.00, 0.40),
    ('tts:l14_announcer.wav', 45.00, 1.00, 0.40),
    ('chime.wav',            50.00, 0.40, 0),
]
for nm, at, g, dk in EV:
    if dk > 0:  # 台词窗口 -> BGM 闪避曲线
        st = int(at * SR); en = min(len(mix), st + int(5.2 * SR))
        d = np.ones(en - st); r = int(0.12 * SR)
        d[:r] = np.linspace(1, 1 - dk, r)
        d[-r:] = np.linspace(1 - dk, 1, r)
        d[r:-r] = 1 - dk
        duckmask[st:en] = np.minimum(duckmask[st:en], d)
def fit(x):
    return np.concatenate([x, np.zeros(len(mix) - len(x))]) if len(x) < len(mix) else x[:len(mix)]
put(fit(load(B0 + '/bgm.wav')) * duckmask, 0.0, 0.95)
put(fit(load(B0 + '/roomtone.wav')) * duckmask, 0.0, 0.30)
for ev in EV:
    nm, at, g, dk = ev
    x = load((TTS if nm.startswith('tts:') else B0) + '/' + nm.replace('tts:', ''))
    if at == 12.55:  # 远处回音版
        x = lp(x, 0.22)
    put(x, at, g)
peak = np.max(np.abs(mix))
if peak > 0.97:
    mix *= 0.97 / peak
with wave.open(B + '/premix.wav', 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((np.clip(mix, -1, 1)*32767).astype('<i2').tobytes())
print('premix %.1fs peak %.2f' % (len(mix) / SR, peak))

# ---------------- 视频渲染（分段，防OOM） ----------------
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
BIGW, BIGH = 2880, 1620

def move_expr(mv, N):
    kind = mv[0]
    if kind == 'zoom':
        _, z0, z1 = mv
        rate = (z1 - z0) / max(N - 1, 1)
        z = "'%s%s*on'" % (z0, ('%+.6f' % rate))
        x = "'iw/2-(iw/zoom/2)'"; y = "'ih/2-(ih/zoom/2)'"
    elif kind == 'zoomtilt':
        _, z0, z1, tilt = mv
        rate = (z1 - z0) / max(N - 1, 1)
        z = "'%s%s*on'" % (z0, ('%+.6f' % rate))
        x = "'iw/2-(iw/zoom/2)'"
        y = "'ih/2-(ih/zoom/2)-(on/(%d))*ih*%s'" % (max(N - 1, 1), tilt)
    elif kind == 'sway':
        _, zv, amp, per = mv
        z = "'%s'" % zv
        x = "'iw/2-(iw/zoom/2)+%s*sin(on/%s)'" % (amp, per)
        y = "'ih/2-(ih/zoom/2)'"
    elif kind == 'shake':
        _, zv = mv
        z = "'%s'" % zv
        x = "'iw/2-(iw/zoom/2)+1.2*sin(on*1.7)+0.8*sin(on*0.9)'"
        y = "'ih/2-(ih/zoom/2)+0.8*sin(on*2.3)'"
    return z, x, y

def render_seg(path, dur, img, mv, sub=None, fade_in=False, fade_out_at=None):
    N = round(dur * FPS)
    z, x, y = move_expr(mv, N)
    base = ('[0:v]scale=%d:%d:flags=lanczos,'
            'zoompan=z=%s:x=%s:y=%s:d=1:s=%dx%d:fps=%d,setsar=1'
            % (BIGW, BIGH, z, x, y, W, H, FPS))
    ins = ['-loop', '1', '-framerate', str(FPS), '-t', str(dur), '-i', img]
    n = 1
    if sub:
        fc = base + '[v]'
        fi, di, fo, do = SUB_FADE[sub]
        ins += ['-loop', '1', '-framerate', str(FPS), '-t', str(dur), '-i', UI + '/' + sub]
        fc += (';[1:v]format=rgba,fade=t=in:st=%s:d=%s:alpha=1,fade=t=out:st=%s:d=%s:alpha=1[s];'
               '[v][s]overlay=0:0' % (fi, di, fo, do))
        n = 2
    else:
        fc = base
    post = ''
    if fade_in:
        post += ',fade=t=in:st=0:d=0.5'
    if fade_out_at is not None:
        post += ',fade=t=out:st=%s:d=0.9' % fade_out_at
    fc += post + ',format=yuv420p[out]'
    cmd = [FF, '-y', '-hide_banner', '-loglevel', 'error'] + ins + [
        '-filter_complex', fc, '-map', '[out]', '-t', str(dur),
        '-r', str(FPS), '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast',
        '-pix_fmt', 'yuv420p', path]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        print('SEG FAIL', path, r.stderr[-800:]); sys.exit(1)
    print('seg', os.path.basename(path), 'ok')

segs = []
for i, (nm, dur, mv, sub) in enumerate(SHOTS):
    p = B + '/seg%02d.mp4' % i
    render_seg(p, dur, src(nm), mv, sub, fade_in=(i == 0))
    segs.append(p)
# 片尾段：床垫定格 + 片尾板 + 淡出
p = B + '/seg14.mp4'
ec_fc_dur = ENDCARD_DUR
z, x, y = move_expr(('zoom', 1.001, 1.001), 1)
ins = ['-loop', '1', '-framerate', str(FPS), '-t', str(ec_fc_dur), '-i', src('shot14_mattress'),
       '-loop', '1', '-framerate', str(FPS), '-t', str(ec_fc_dur), '-i', UI + '/endcard.png']
fc = ('[0:v]scale=%d:%d:flags=lanczos,setsar=1[v];'
      '[1:v]format=rgba,fade=t=in:st=0.1:d=0.6:alpha=1[ec];'
      '[v][ec]overlay=0:0,fade=t=out:st=%s:d=0.9,format=yuv420p[out]'
      % (W, H, ec_fc_dur - 1.0))
cmd = [FF, '-y', '-hide_banner', '-loglevel', 'error'] + ins + [
    '-filter_complex', fc, '-map', '[out]', '-t', str(ec_fc_dur),
    '-r', str(FPS), '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', p]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode:
    print('ENDCARD FAIL', r.stderr[-800:]); sys.exit(1)
segs.append(p)
print('seg endcard ok')

with open(B + '/list.txt', 'w') as f:
    for s in segs:
        f.write("file '%s'\n" % s)
cmd = [FF, '-y', '-hide_banner', '-loglevel', 'error',
       '-f', 'concat', '-safe', '0', '-i', B + '/list.txt',
       '-i', B + '/premix.wav',
       '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
       '-movflags', '+faststart', '-shortest', OUT + '/白蛇酒变_v1.mp4']
r = subprocess.run(cmd, capture_output=True, text=True)
print(r.stderr[-800:] if r.returncode else 'RENDER OK')
if r.returncode:
    sys.exit(1)
print('DONE ->', OUT + '/白蛇酒变_v1.mp4', os.path.getsize(OUT + '/白蛇酒变_v1.mp4') // 1024, 'KB')
