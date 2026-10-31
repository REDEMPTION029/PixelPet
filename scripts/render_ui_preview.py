"""Render the countdown panel to a PNG without creating or controlling a window."""
from pathlib import Path
import ctypes as C
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from import_sheets import encode
from src import native_api as n
from src.focus_overlay import PanelPainter


def main():
    imaging=n.Imaging();painter=PanelPainter()
    w,h=300,484
    image=bytearray(w*h*4)
    for y in range(h):
        for x in range(w):
            c=246 if (x//12+y//12)%2 else 235
            p=(y*w+x)*4;image[p:p+4]=bytes((c,c, min(255,c+5),255))
    try:
        for row,args in enumerate(((1499,'focus',False,1),(1494,'focus',False,0),(1470,'focus',True,.5),(300,'break',False,1))):
            surface=painter.surface(*args)
            pixels=C.string_at(surface.bits,surface.width*surface.height*4)
            for y in range(surface.height):
                for x in range(surface.width):
                    source=(y*surface.width+x)*4;dest=((y+10+row*119)*w+x+32)*4
                    b,g,r,a=pixels[source:source+4]
                    for channel,value in enumerate((r,g,b)):
                        image[dest+channel]=min(255,value+round(image[dest+channel]*(255-a)/255))
        encode(ROOT/'docs/countdown-panel-preview.png',w,h,image)
    finally:painter.close();imaging.close()
    print('Rendered panel preview offscreen; no windows, mouse or keyboard used.')


if __name__=='__main__':main()
