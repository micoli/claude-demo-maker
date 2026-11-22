"""Compose cached transparent avatar frames with circular office portraits."""
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont, ImageOps

out, job_path = (Path(arg).resolve() for arg in sys.argv[1:])
job = json.loads(job_path.read_text())
timeline = json.loads((out/'timeline.json').read_text())
actors = list(job['actors'])
colors = ('#86c9b5', '#83b6e8', '#c4ade8', '#e0b78b')
diameter, portrait_top, centers = {
    2: (504, 151, (466, 1134)),
    3: (402, 210, (300, 800, 1300)),
    4: (316, 259, (230, 610, 990, 1370)),
}[len(actors)]

def font(size):
    custom = os.environ.get('AVATAR_FONT')
    if custom:
        return ImageFont.truetype(custom, size)
    try:
        return ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', size)
    except OSError:
        return ImageFont.load_default(size=size)

background = Image.new('RGB', (400, 225))
pixels = background.load()
for y in range(225):
    for x in range(400):
        left = math.exp(-((x-90)/123)**2-((y-75)/101)**2)
        right = math.exp(-((x-303)/111)**2-((y-78)/100)**2)
        top = 1-y/225
        pixels[x,y] = (int(13+10*left+7*right+6*top),
                       int(23+16*left+20*right+8*top),
                       int(36+27*left+23*right+10*top))
background = background.resize((1600, 900), Image.Resampling.BICUBIC)
draw = ImageDraw.Draw(background)
title = job.get('title', 'Dialogue in English' if timeline['language'].split('-')[0] == 'en' else 'Dialogue')
draw.text((800, portrait_top-78), title, font=font(38), fill='#f1f5fa', anchor='mm')
draw.line((124, portrait_top-36, 1476, portrait_top-36), fill='#43566b')
for x, actor in zip(centers, actors):
    draw.text((x, portrait_top+diameter+37), job['actors'][actor]['label'], font=font(30),
              fill='#f1f5fa', anchor='mm')
draw.rounded_rectangle((180, 754, 1420, 879), radius=18, fill='#0b1625', outline='#32465a')
background.save(out/'background.png')

def disk(inset):
    mask = Image.new('L', (diameter*4, diameter*4))
    ImageDraw.Draw(mask).ellipse((inset*4, inset*4, (diameter-inset)*4-1, (diameter-inset)*4-1), fill=255)
    return mask.resize((diameter, diameter), Image.Resampling.LANCZOS)

outer, inner = disk(0), disk(2)
border = Image.new('RGBA', inner.size, '#7e91a3')
border.putalpha(outer)
background_dir = Path(__file__).resolve().parents[1]/'assets/background'
images = {p.name: p for p in sorted(background_dir.iterdir()) if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'}}
selection_path = out/'background-selection.json'
previous = json.loads(selection_path.read_text()) if selection_path.is_file() else {}
selection = {}
for actor in actors:
    explicit = job['actors'][actor].get('background')
    if explicit:
        if explicit not in images:
            raise ValueError(f'Unknown portrait background: {explicit}')
        selection[actor] = explicit
    elif previous.get(actor) in images and previous[actor] not in selection.values():
        selection[actor] = previous[actor]
for actor in actors:
    if actor not in selection:
        choices = sorted(set(images).difference(selection.values()))
        selection[actor] = random.choice(choices or list(images))
selection_path.write_text(json.dumps(selection, indent=2)+'\n')

frames_root = out/'portraits'
for actor, color in zip(actors, colors):
    with Image.open(images[selection[actor]]) as image:
        interior = ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'), inner.size,
                                method=Image.Resampling.LANCZOS).convert('RGBA')
    path = frames_root/actor
    path.mkdir(parents=True, exist_ok=True)
    ring = Image.new('RGBA', (diameter*4, diameter*4))
    ImageDraw.Draw(ring).ellipse((1, 1, diameter*4-2, diameter*4-2), outline=color, width=12)
    ring.resize(inner.size, Image.Resampling.LANCZOS).save(out/f'{actor}-ring.png')
    known = {}
    scale = round(diameter * 864/504)
    offset = ((diameter-scale)//2, -round(diameter*113/504))
    for frame in sorted((out/'actors'/actor).glob('f_*.png')):
        target = path/frame.name
        target.unlink(missing_ok=True)
        info = frame.stat()
        key = (info.st_dev, info.st_ino)
        if key in known:
            os.link(known[key], target)
            continue
        with Image.open(frame) as source:
            avatar = source.convert('RGBA').resize((scale,scale), Image.Resampling.LANCZOS)
        portrait = interior.copy()
        portrait.alpha_composite(avatar, offset)
        portrait.putalpha(inner)
        Image.alpha_composite(border, portrait).save(target, compress_level=1)
        known[key] = target

ass = (out/'dialogue.ass').read_text().replace(',2,60,60,28,1', ',2,202,202,40,1')
(out/'subtitles-circles.ass').write_text(ass)
filters = []
chain = '0:v'
for index, (actor, center) in enumerate(zip(actors, centers)):
    x = center-diameter//2
    times = '+'.join(f"between(t,{line['start']:.6f},{line['end']:.6f})" for line in timeline['lines'] if line['speaker']==actor) or '0'
    filters.append(f'[{chain}][{index+1}:v]overlay={x}:{portrait_top}:shortest=1[p{index}]')
    filters.append(f"[p{index}][{index+1+len(actors)}:v]overlay={x}:{portrait_top}:enable='{times}'[v{index}]")
    chain = f'v{index}'
filters.append(f'[{chain}]ass=subtitles-circles.ass,format=yuv420p[out]')
subprocess.run([
    'ffmpeg', '-v','error','-y','-loop','1','-framerate','25','-i','background.png',
    *[arg for actor in actors for arg in ('-framerate','25','-i',f'portraits/{actor}/f_%04d.png')],
    *[arg for actor in actors for arg in ('-i',f'{actor}-ring.png')],
    '-i','voice.wav','-filter_complex_threads','2','-filter_complex',';'.join(filters),
    '-map','[out]','-map',f'{1+2*len(actors)}:a:0','-t',str(timeline['total']),
    '-c:v','libx264','-preset','fast','-crf','19','-c:a','aac','-b:a','160k',
    '-af','loudnorm=I=-16:TP=-1.5:LRA=7','-ar','48000','-movflags','+faststart','dialogue.mp4',
], cwd=out, check=True)
