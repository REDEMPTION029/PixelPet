"""Crop and align GPT-drawn poses. No synthetic movement or character redrawing."""
from pathlib import Path
from collections import deque
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.import_sheets import decode,encode
from src.native_model import resample


def bounds_of_main_sprite(w,h,data,box):
    x0,y0,x1,y1=box
    remaining={(x,y) for y in range(y0,y1) for x in range(x0,x1) if data[(y*w+x)*4+3]>=128}
    largest=[]
    while remaining:
        start=remaining.pop();queue=deque([start]);component=[start]
        while queue:
            x,y=queue.popleft()
            for point in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if point in remaining:
                    remaining.remove(point);queue.append(point);component.append(point)
        if len(component)>len(largest):largest=component
    if len(largest)<1000:raise ValueError('Missing main character in sprite cell')
    return (max(x0,min(p[0] for p in largest)-2),max(y0,min(p[1] for p in largest)-2),
            min(x1,max(p[0] for p in largest)+3),min(y1,max(p[1] for p in largest)+3))


def main():
    records=[]
    for source,cols,rows,scale in [('run-v070-a.png',4,2,1.06),('run-v070-b.png',2,2,.78)]:
        w,h,data=decode(ROOT/'assets/sheets'/source)
        for i in range(4):
            box=(round((i%cols)*w/cols),round((i//cols)*h/rows),
                 round((i%cols+1)*w/cols),round((i//cols+1)*h/rows))
            x0,y0,x1,y1=bounds_of_main_sprite(w,h,data,box)
            cw,ch=x1-x0,y1-y0
            raw=b''.join(data[(y*w+x0)*4:(y*w+x1)*4] for y in range(y0,y1))
            rw,rh,pixels=resample((cw,ch,raw),scale,False)
            head=[x for y in range(y0,y0+round(ch*.22)) for x in range(x0,x1) if data[(y*w+x)*4+3]>=128]
            head_centre=(min(head)+max(head))/2-x0
            dx=max(0,min(512-rw,round(224-head_centre*scale)))
            dy=30+[0,2,-1,-4][i]
            assert rw<=512 and dy+rh<=512,(source,i,rw,rh)
            packed=bytearray(512*512*4)
            for y in range(rh):
                start=((y+dy)*512+dx)*4
                packed[start:start+rw*4]=pixels[y*rw*4:(y+1)*rw*4]
            index=len(records)+1
            encode(ROOT/f'assets/walk/walk_{index:02}.png',512,512,packed)
            records.append({'source':source,'cell':i,'bbox':[x0,y0,x1,y1],'scale':scale,'placement':[dx,dy]})
    path=ROOT/'assets/frame_meta.json';meta=json.loads(path.read_text(encoding='utf-8'))
    meta['walk'].update(frame_durations_ms=[85,75,65,75]*2,anchors=[[256,496]]*8,cycle_distance=96)
    meta['dragRun'].update(frame_files=[f'walk/walk_{i:02}.png' for i in range(1,9)],
        frame_durations_ms=[95,85,75,85]*2,anchors=[[256,496]]*8)
    meta['walkEnter'].update(frame_files=['idle/idle_01.png','walk/walk_02.png'])
    meta['walkExit'].update(frame_files=['walk/walk_06.png','idle/idle_01.png'])
    path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'docs/asset_report_v0.7.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    print('Imported eight GPT poses; walk cycle 600ms, drag cycle 680ms, authored stride 96px.')


if __name__=='__main__':main()
