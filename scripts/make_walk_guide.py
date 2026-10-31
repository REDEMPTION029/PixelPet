"""Draw an original geometric pose guide for GPT; contains no character pixels."""
from pathlib import Path
from import_sheets import encode

ROOT = Path(__file__).resolve().parents[1]


def main():
    w, h = 1536, 1024
    data = bytearray(bytes((250, 250, 250, 255)) * (w * h))
    def disc(x, y, r, color):
        for yy in range(max(0, y-r), min(h, y+r+1)):
            for xx in range(max(0, x-r), min(w, x+r+1)):
                if (xx-x)**2 + (yy-y)**2 <= r*r:
                    p=(yy*w+xx)*4;data[p:p+4]=bytes((*color,255))
    def line(a,b,color,r=9):
        dx,dy=b[0]-a[0],b[1]-a[1]
        steps=max(abs(dx),abs(dy),1)
        for i in range(steps+1):
            disc(round(a[0]+dx*i/steps),round(a[1]+dy*i/steps),r,color)
    # Red is one anatomical leg, cyan is the other; positions exchange in the second half.
    poses=[((150,408),(112,478),(226,412),(260,470)),
           ((165,420),(147,478),(222,392),(254,444)),
           ((185,421),(188,478),(190,385),(222,430)),
           ((216,415),(247,472),(162,405),(132,463)),
           ((225,412),(260,470),(156,408),(112,478)),
           ((216,392),(254,444),(171,420),(147,478)),
           ((194,385),(222,430),(196,421),(188,478)),
           ((162,405),(132,463),(210,415),(247,472))]
    for i,(rk,rf,bk,bf) in enumerate(poses):
        ox,oy=i%4*384,i//4*512
        def pt(p):return (p[0]+ox,p[1]+oy)
        disc(192+ox,145+oy,98,(220,220,228))
        line(pt((192,250)),pt((192,349)),(45,55,85),25)
        line(pt((165,349)),pt((217,349)),(45,55,85),11)
        line(pt((180,349)),pt(rk),(220,70,75),12);line(pt(rk),pt(rf),(220,70,75),12)
        line(pt((204,349)),pt(bk),(40,155,200),12);line(pt(bk),pt(bf),(40,155,200),12)
        disc(*pt(rf),16,(220,70,75));disc(*pt(bf),16,(40,155,200))
        line(pt((165,275)),pt((145 if i<4 else 234,335)),(90,90,110),8)
        line(pt((219,275)),pt((234 if i<4 else 145,335)),(90,90,110),8)
    (ROOT/'build').mkdir(exist_ok=True)
    encode(ROOT/'build/walk-pose-guide.png',w,h,data)
    print('Created 8-pose geometric guide, with genuinely opposite support legs.')


if __name__=='__main__':main()
