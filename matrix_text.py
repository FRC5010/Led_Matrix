#!/usr/bin/env python3
"""Crisp pixel text for the 16-wide x 14-high WS2815 matrix + Uno R3.

Install: python -m pip install pyserial
Run:     python matrix_text.py --text "HELLO TEAM!"
Check:   python matrix_text.py --text "HI" --static
Options: python matrix_text.py --help

Uses the existing MatrixBridge sketch: COUNT must be 224. No new firmware
needed if that change is already uploaded. This program uses the existing
M14! + RGB + checksum protocol at 115200 baud, waiting for K after each frame.
Do not run the old matrix.py or a serial monitor at the same time.

All lowercase is converted to uppercase. Supported characters: A-Z, 0-9,
spaces and common punctuation. Unsupported characters become question marks.
Font pixels are strictly on/off, with no antialiasing. Default brightness 10%.
Ctrl+C clears the display. Existing Uno firmware clears after 5s without data.
"""
import argparse
import math
import struct
import sys
import time
import unicodedata

# Each glyph is seven rows, five bits per row. Our own simple block lettering.
FONT_ROWS = {
    'A': '0E 11 11 1F 11 11 11', 'B': '1E 11 11 1E 11 11 1E',
    'C': '0E 11 10 10 10 11 0E', 'D': '1E 11 11 11 11 11 1E',
    'E': '1F 10 10 1E 10 10 1F', 'F': '1F 10 10 1E 10 10 10',
    'G': '0E 11 10 17 11 11 0F', 'H': '11 11 11 1F 11 11 11',
    'I': '0E 04 04 04 04 04 0E', 'J': '07 02 02 02 12 12 0C',
    'K': '11 12 14 18 14 12 11', 'L': '10 10 10 10 10 10 1F',
    'M': '11 1B 15 15 11 11 11', 'N': '11 19 15 13 11 11 11',
    'O': '0E 11 11 11 11 11 0E', 'P': '1E 11 11 1E 10 10 10',
    'Q': '0E 11 11 11 15 12 0D', 'R': '1E 11 11 1E 14 12 11',
    'S': '0F 10 10 0E 01 01 1E', 'T': '1F 04 04 04 04 04 04',
    'U': '11 11 11 11 11 11 0E', 'V': '11 11 11 11 11 0A 04',
    'W': '11 11 11 15 15 1B 11', 'X': '11 11 0A 04 0A 11 11',
    'Y': '11 11 0A 04 04 04 04', 'Z': '1F 01 02 04 08 10 1F',
    '0': '0E 11 13 15 19 11 0E', '1': '04 0C 04 04 04 04 0E',
    '2': '0E 11 01 02 04 08 1F', '3': '1E 01 01 0E 01 01 1E',
    '4': '02 06 0A 12 1F 02 02', '5': '1F 10 10 1E 01 01 1E',
    '6': '0E 10 10 1E 11 11 0E', '7': '1F 01 02 04 08 08 08',
    '8': '0E 11 11 0E 11 11 0E', '9': '0E 11 11 0F 01 01 0E',
    '!': '04 04 04 04 04 00 04', '?': '0E 11 01 02 04 00 04',
    '.': '00 00 00 00 00 00 04', ',': '00 00 00 00 00 04 08',
    ':': '00 04 04 00 04 04 00', ';': '00 04 04 00 04 04 08',
    '-': '00 00 00 1F 00 00 00', '_': '00 00 00 00 00 00 1F',
    '+': '00 04 04 1F 04 04 00', '=': '00 00 1F 00 1F 00 00',
    '/': '01 02 02 04 08 08 10', '\\': '10 08 08 04 02 02 01',
    "'": '04 04 08 00 00 00 00', '"': '0A 0A 00 00 00 00 00',
    '(': '02 04 08 08 08 04 02', ')': '08 04 02 02 02 04 08',
    '[': '0E 08 08 08 08 08 0E', ']': '0E 02 02 02 02 02 0E',
    '<': '01 02 04 08 04 02 01', '>': '10 08 04 02 04 08 10',
    '#': '0A 0A 1F 0A 1F 0A 0A', '*': '00 15 0E 1F 0E 15 00',
    '%': '19 19 02 04 08 13 13', '&': '0C 12 14 08 15 12 0D',
    '@': '0E 11 17 15 17 10 0E', '$': '04 0F 14 0E 05 1E 04',
}
COLORS = {
    'white': (255,255,255), 'red': (255,0,0), 'green': (0,255,0),
    'blue': (0,0,255), 'cyan': (0,255,255), 'yellow': (255,255,0),
    'orange': (255,100,0), 'purple': (160,0,255), 'pink': (255,0,100),
}


def color_value(value):
    value = value.lower()
    if value in COLORS:
        return COLORS[value]
    try:
        value = value.lstrip('#')
        if len(value) != 6:
            raise ValueError()
        return tuple(int(value[i:i+2],16) for i in (0,2,4))
    except ValueError:
        raise argparse.ArgumentTypeError('Use a color name or a hex color such as FF8000.')


def normalize_text(text):
    text = text.translate(str.maketrans({'’': "'", '‘': "'", '“': '"', '”': '"', '–': '-', '—': '-'}))
    text = unicodedata.normalize('NFKD', text.upper())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return ''.join(' ' if c.isspace() else c if c in FONT_ROWS else '?' for c in text)


def text_columns(text, spacing=1, scale=1):
    """Return vertical bit columns with bit zero at the top; trim empty sides."""
    result = []
    for index, char in enumerate(normalize_text(text)):
        if index:
            result.extend([0] * spacing * scale)
        if char == ' ':
            cols = [0] * 3
        else:
            rows = [int(v,16) for v in FONT_ROWS[char].split()]
            cols = [sum(((rows[y] >> (4-x)) & 1) << y for y in range(7)) for x in range(5)]
            while cols and cols[0] == 0:
                cols.pop(0)
            while cols and cols[-1] == 0:
                cols.pop()
        for col in cols:
            enlarged = sum(((1 << scale)-1) << (y*scale) for y in range(7) if col & (1 << y))
            result.extend([enlarged]*scale)
    return result


def physical_positions(width, height, axis, corner, serpentine=True):
    strips, length = (width,height) if axis == 'columns' else (height,width)
    for strip in range(strips):
        for step in range(length):
            along = length-1-step if serpentine and strip % 2 else step
            x,y = (strip,along) if axis == 'columns' else (along,strip)
            if corner.endswith('r'):
                x = width-1-x
            if corner.startswith('b'):
                y = height-1-y
            yield x,y


def render(columns, offset, width, height, scale, rgb):
    """Logical top-left origin RGB canvas; only whole physical pixels are used."""
    frame = bytearray(width*height*3)
    top = (height-7*scale)//2
    for x in range(width):
        source = x-offset
        if 0 <= source < len(columns):
            bits = columns[source]
            for y in range(7*scale):
                if bits & (1 << y):
                    start = ((top+y)*width+x)*3
                    frame[start:start+3] = bytes(rgb)
    return frame


def pack_pixels(frame, width, coords):
    data = bytearray()
    for x,y in coords:
        index = (y*width+x)*3
        data.extend(frame[index:index+3])
    return bytes(data)


def make_packet(data):
    return b'M14!' + data + struct.pack('<H',sum(data) & 65535)


class Bridge:
    def __init__(self, port):
        try:
            import serial
        except ImportError as exc:
            raise RuntimeError('Install pyserial in your active environment: python -m pip install pyserial') from exc
        self.port = serial.Serial(port,115200,timeout=3,write_timeout=3)
        try:
            time.sleep(2.5) # Opening a normal Uno resets it; allow bootloader to finish.
            self.port.reset_input_buffer()
        except BaseException:
            self.port.close()
            raise

    def send(self, data):
        self.port.write(make_packet(data))
        reply = self.port.read(1)
        if reply == b'N':
            raise RuntimeError('Uno rejected a frame. Check its uploaded COUNT is 224, and check USB/power. Restart this program after fixing it.')
        if reply != b'K':
            raise RuntimeError(f'No valid Uno acknowledgment ({reply!r}). Check port and MatrixBridge upload; close other serial programs.')

    def close(self):
        self.port.close()


def frame_stream(args, columns, rgb):
    coords = list(physical_positions(args.width,args.height,args.axis,args.corner,not args.straight))
    if args.test:
        if args.test == 'chase':
            while True:
                for index,(x,y) in enumerate(coords):
                    frame=bytearray(args.width*args.height*3)
                    start=(y*args.width+x)*3
                    frame[start:start+3]=bytes(rgb)
                    print(f'LED {index+1}/{len(coords)} at x={x}, y={y}',flush=True)
                    yield frame, 0.5
                if args.once:
                    return
        else:
            frame=bytearray(args.width*args.height*3)
            for (x,y),color in [((0,0),COLORS['red']),((args.width-1,0),COLORS['green']),((0,args.height-1),COLORS['blue']),((args.width-1,args.height-1),COLORS['white'])]:
                start=(y*args.width+x)*3
                frame[start:start+3]=bytes(round(c*args.brightness) for c in color)
            print('Corners: red TL, green TR, blue BL, white BR.',flush=True)
            while True:
                yield frame, 1.0
                if args.once:
                    return
    elif args.static:
        frame=render(columns,(args.width-len(columns))//2,args.width,args.height,args.scale,rgb)
        while True:
            yield frame,1.0 # Keep the firmware watchdog alive.
            if args.once:
                return
    else:
        while True:
            offsets=range(args.width,-len(columns)-1,-1) if args.direction=='left' else range(-len(columns),args.width+1)
            for offset in offsets:
                yield render(columns,offset,args.width,args.height,args.scale,rgb),1/args.speed
            # Send blank keepalive frames during a long inter-message pause.
            left=args.pause
            while left > 0:
                duration=min(left,1.0)
                yield bytearray(args.width*args.height*3),duration
                left-=duration
            if args.once:
                return


def arguments():
    p=argparse.ArgumentParser(description='Crisp block text for a 16x14 matrix. Uses your existing Uno MatrixBridge sketch.',formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('--text',default='HELLO TEAM!')
    p.add_argument('--port',default='/dev/ttyACM0')
    p.add_argument('--width',type=int,default=16)
    p.add_argument('--height',type=int,default=14)
    p.add_argument('--axis',choices=['columns','rows'],default='columns')
    p.add_argument('--corner',choices=['tl','tr','bl','br'],default='tl',help='First LED location viewed from LED side')
    p.add_argument('--straight',action='store_true',help='Use only if every strip runs the same direction; default is zigzag')
    p.add_argument('--speed',type=float,default=6,help='Whole pixels per second, 1-12')
    p.add_argument('--color',type=color_value,default=COLORS['white'],help='white, red, green, blue, cyan, yellow, orange, purple, pink, or RRGGBB')
    p.add_argument('--brightness',type=float,default=0.10,help='0 to 1; keep low until power wiring is verified')
    p.add_argument('--spacing',type=int,default=1,help='Blank columns between letters before scaling, 0-5')
    p.add_argument('--scale',type=int,choices=[1,2],default=1,help='1 = 7-pixel-high letters; 2 = 14-pixel-high letters')
    p.add_argument('--pause',type=float,default=0.5,help='Seconds between repeated messages, 0-60')
    p.add_argument('--direction',choices=['left','right'],default='left')
    p.add_argument('--static',action='store_true',help='Center a short word without scrolling; long text is rejected')
    p.add_argument('--once',action='store_true',help='One scroll/pass; static/corners display for one second then clear')
    p.add_argument('--test',choices=['corners','chase'],help='Diagnostic pattern instead of text')
    p.add_argument('--preview',metavar='FILE.gif',help='Save simulated scrolling GIF (requires Pillow); does not open USB')
    args=p.parse_args()
    if args.width < 1 or args.height < 1 or args.width*args.height != 224:
        p.error('Dimensions must be positive and multiply to 224 to match your Uno sketch.')
    if not args.test and 7*args.scale > args.height:
        p.error('Font height exceeds the matrix height. Use --scale 1.')
    if not math.isfinite(args.speed) or not 1 <= args.speed <= 12:
        p.error('--speed must be 1 to 12.')
    if not math.isfinite(args.brightness) or not 0 <= args.brightness <= 1:
        p.error('--brightness must be 0 to 1.')
    if not math.isfinite(args.pause) or not 0 <= args.pause <= 60:
        p.error('--pause must be 0 to 60.')
    if not 0 <= args.spacing <= 5:
        p.error('--spacing must be 0 to 5.')
    if not args.test and (not args.text.strip() or len(args.text)>500):
        p.error('Use a nonempty message of at most 500 characters.')
    columns=text_columns(args.text,args.spacing,args.scale)
    if not args.test and args.static and len(columns)>args.width:
        p.error('Static text is too wide. Try --text "HI", --scale 1, or omit --static to scroll.')
    if args.preview and not args.preview.lower().endswith('.gif'):
        p.error('--preview filename must end in .gif')
    if args.preview and len(columns)>600:
        p.error('Use a shorter message for GIF preview (rendered width must be at most 600 pixels).')
    return args,columns


def save_preview(args,columns):
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError('Preview needs Pillow: python -m pip install pillow') from exc
    args.once=True
    frames=[]
    durations=[]
    # Preview is bright enough to inspect; actual LEDs still use --brightness.
    for frame,duration in frame_stream(args,columns,args.color):
        im=Image.frombytes('RGB',(args.width,args.height),bytes(frame))
        frames.append(im.resize((args.width*20,args.height*20),Image.Resampling.NEAREST))
        durations.append(max(20,round(duration*1000/10)*10))
    frames[0].save(args.preview,save_all=True,append_images=frames[1:],duration=durations,loop=0,disposal=2)
    print(f'Saved simulated preview: {args.preview}. This shows intended pixels, not actual wiring.')


def main():
    args,columns=arguments()
    bridge=None
    healthy=True
    try:
        if args.preview:
            save_preview(args,columns)
            return 0
        coords=list(physical_positions(args.width,args.height,args.axis,args.corner,not args.straight))
        rgb=tuple(round(c*args.brightness) for c in args.color)
        bridge=Bridge(args.port)
        print(f'{args.width}x{args.height}, {args.axis}, first LED {args.corner}, brightness {args.brightness:.0%}. Ctrl+C clears and stops.',flush=True)
        if not args.test:
            print(f'Text: {normalize_text(args.text)}',flush=True)
        for frame,duration in frame_stream(args,columns,rgb):
            start=time.monotonic()
            bridge.send(pack_pixels(frame,args.width,coords))
            time.sleep(max(0,duration-(time.monotonic()-start)))
    except KeyboardInterrupt:
        print('\nStopped.')
    except Exception as exc:
        healthy=False
        print(f'Error: {exc}',file=sys.stderr)
        print('If the port is busy, close matrix.py and Serial Monitor. If permission is denied, check dialout membership.',file=sys.stderr)
        return 1
    finally:
        if bridge is not None:
            if healthy:
                try:
                    bridge.send(bytes(args.width*args.height*3))
                except Exception:
                    print('Could not clear. Existing Uno firmware should blank after its 5-second timeout.',file=sys.stderr)
            bridge.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
