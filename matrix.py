#!/usr/bin/env python3
"""14x14 RGB matrix via USB Uno bridge. Run --help for options."""
import argparse
import struct
import time
from pathlib import Path
import serial
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageColor
W = 16
H = 14

def positions(axis, corner):
    strips = W if axis == 'columns' else H
    length = H if axis == 'columns' else W
    # Physical coordinates viewed from the LED/front side.
    for strip in range(strips):
        for step in range(length):
            along = step if strip % 2 == 0 else length - 1 - step
            x, y = (strip, along) if axis == 'columns' else (along, strip)
            if corner.endswith('r'): x = W - 1 - x
            if corner.startswith('b'): y = H - 1 - y
            yield x, y

def encode(im, coords, brightness):
    return bytes(round(c * brightness) for xy in coords for c in im.getpixel(xy))

def send_frame(port, data):
    packet = b'M14!' + data + struct.pack('<H', sum(data) & 65535)
    port.write(packet)
    reply = port.read(1)
    if reply != b'K':
        raise RuntimeError(f'Uno did not acknowledge frame (received {reply!r}). Restart the program; check USB, sketch and power.')

def content(args):
    if args.mode == 'text':
        font = ImageFont.truetype(args.font, args.font_size)
        box = font.getbbox(args.text or ' ')
        im = Image.new('RGB', (max(1, box[2]-box[0]), H))
        ImageDraw.Draw(im).text((-box[0], (H-(box[3]-box[1]))//2-box[1]), args.text, font=font, fill='white')
        return im
    with Image.open(args.image) as original:
        rgba = ImageOps.exif_transpose(original).convert('RGBA')
        im = Image.new('RGBA', rgba.size, 'black')
        im.alpha_composite(rgba)
        im = im.convert('RGB')
    if args.fit:
        small = ImageOps.contain(im, (W,H), Image.Resampling.NEAREST)
        canvas = Image.new('RGB',(W,H))
        canvas.paste(small, ((W-small.width)//2,(H-small.height)//2))
        return canvas
    return im.resize((max(1, round(im.width*H/im.height)),H),Image.Resampling.NEAREST)

def frames(args, coords):
    if args.mode == 'test':
        for name in ('red','green','blue'):
            print(f'Whole panel: {name}', flush=True)
            for _ in range(max(1,round(args.fps))): yield Image.new('RGB',(W,H),name)
        print('Corners: red top-left, green top-right, blue bottom-left, white bottom-right.', flush=True)
        im = Image.new('RGB',(W,H))
        for xy,c in [((0,0),'red'),((W - 1,0),'green'),((0,H - 1),'blue'),((W - 1,H - 1),'white')]: im.putpixel(xy, ImageColor.getrgb(c))
        for _ in range(max(1,round(4*args.fps))): yield im
        print('One white pixel follows the physical wire from first LED to last.', flush=True)
        for xy in coords:
            im = Image.new('RGB',(W,H)); im.putpixel(xy,(255,255,255)); yield im
    else:
        im = content(args)
        if args.mode == 'image' and args.fit:
            while True: yield im
        while True:
            for x in range(W, -im.width-1, -1):
                canvas = Image.new('RGB',(W,H)); canvas.paste(im,(x,0)); yield canvas

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',required=True)
    p.add_argument('--axis',choices=['columns','rows'],default='columns')
    p.add_argument('--corner',choices=['tl','tr','bl','br'],default='tl',help='Location of FIRST LED, viewed from front')
    p.add_argument('--brightness',type=float,default=0.10,help='0 to 1; start low')
    p.add_argument('--fps',type=float,default=10,help='Frames per second, 1 to 15')
    p.add_argument('mode',choices=['test','text','image'])
    p.add_argument('--text',default='HELLO!')
    p.add_argument('--image')
    p.add_argument('--fit',action='store_true',help='Show entire image stationary')
    p.add_argument('--font',default='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')
    p.add_argument('--font-size',type=int,default=11)
    args=p.parse_args()
    if not 0 <= args.brightness <= 1: p.error('brightness must be 0 to 1')
    if not 1 <= args.fps <= 15: p.error('fps must be 1 to 15')
    if args.mode=='image' and not args.image: p.error('image mode needs --image FILE')
    if args.mode=='text' and not Path(args.font).is_file(): p.error('Font missing. Install fonts-dejavu-core or supply --font FILE')
    coords=list(positions(args.axis,args.corner))
    with serial.Serial(args.port,115200,timeout=3,write_timeout=3) as port:
        # Opening USB serial normally resets an Uno. Wait for its bootloader.
        time.sleep(2.5)
        port.reset_input_buffer()
        print('Connected. Ctrl+C stops and clears the display.',flush=True)
        try:
            for im in frames(args,coords):
                start=time.monotonic()
                send_frame(port,encode(im,coords,args.brightness))
                time.sleep(max(0,1/args.fps-(time.monotonic()-start)))
        except KeyboardInterrupt:
            pass
        finally:
            try: send_frame(port,bytes(W*H*3))
            except (RuntimeError,serial.SerialException): pass

if __name__=='__main__':
    main()
