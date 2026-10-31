"""Import GPT-drawn held, peeking and alternate-support walking sprites."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from import_sheets import decode,encode
from src.native_model import resample


def main():
    recipes={"peek":("peek-v052.png",.78,[0,1,3]),
             "walk":("run-v052.png",.82,[0,1,2,3])}
    report={}
    for action,(source,scale,selection) in recipes.items():
        w,h,data=decode(ROOT/'assets/sheets'/source)
        assert w==h and w%2==0
        cell=w//2
        folder=ROOT/'assets'/action;folder.mkdir(exist_ok=True)
        records=[]
        for output,i in enumerate(selection,1):
            ox,oy=i%2*cell,i//2*cell
            coords=[(x,y) for y in range(oy,oy+cell) for x in range(ox,ox+cell) if data[(y*w+x)*4+3]>=128]
            x0,y0=min(x for x,y in coords)-2,min(y for x,y in coords)-2
            x1,y1=max(x for x,y in coords)+3,max(y for x,y in coords)+3
            x0,y0,x1,y1=max(ox,x0),max(oy,y0),min(ox+cell,x1),min(oy+cell,y1)
            cw,ch=x1-x0,y1-y0
            raw=b''.join(data[(y*w+x0)*4:(y*w+x1)*4] for y in range(y0,y1))
            rw,rh,pixels=resample((cw,ch,raw),scale,False)
            if action=='peek':
                # The drawn vertical grip line is just right of the leftmost fingers.
                source_grip=x0+15
                dx=round(160-(source_grip-x0)*rw/cw);dy=24
            else:
                dx=round(256-rw/2);dy=(472 if action=='held' else 496)-rh
            assert dx>=0 and dy>=0 and dx+rw<=512 and dy+rh<=512,(action,i,dx,dy,rw,rh)
            packed=bytearray(512*512*4)
            for y in range(rh):
                start=((dy+y)*512+dx)*4
                packed[start:start+rw*4]=pixels[y*rw*4:(y+1)*rw*4]
            encode(folder/f'{action}_{output:02}.png',512,512,packed)
            records.append({'source_cell':i,'source_bbox':[x0,y0,x1,y1],'placement':[dx,dy],'scale':scale})
        # Only stale exported walk frames are removed; the old set is in the baseline ZIP.
        if action in ('walk','peek'):
            for stale in folder.glob(f'{action}_*.png'):
                if int(stale.stem.rsplit('_',1)[1])<=len(selection):continue
                assert stale.resolve().is_relative_to(folder.resolve())
                if stale.exists():stale.unlink()
        report[action]=records
    path=ROOT/'assets/frame_meta.json';meta=json.loads(path.read_text(encoding='utf-8'))
    meta.pop('held',None)
    meta['dragRun']={'frame_files':[f'walk/walk_{i:02}.png' for i in range(1,5)],'duration_ms':170,
        'frame_durations_ms':[190,150,190,150],'loop':True,'next':None,'anchors':[[256,496]]*4,'base_facing':'left'}
    meta['peek']={'duration_ms':300,'frame_durations_ms':[1800,110,1500],'loop':True,'next':None,'anchors':[[256,496]]*3,'grip_x':160,'base_facing':'right','gaze':'viewer'}
    meta['walk'].update(frame_durations_ms=[170,130,170,130],anchors=[[256,496]]*4,cycle_distance=64)
    # Feet pass through a neutral frame at both boundaries instead of retaining an old lifted pose.
    meta['walkEnter'].update(frame_files=['idle/idle_01.png','walk/walk_01.png'])
    meta['walkExit'].update(frame_files=['walk/walk_03.png','idle/idle_01.png'])
    (ROOT/'docs/asset_report_v0.5.2.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    meta['walk']['base_facing']='left'
    path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Imported viewer-facing peek3 / three-quarter run4. Added fast dragRun4.')


if __name__=='__main__':main()
