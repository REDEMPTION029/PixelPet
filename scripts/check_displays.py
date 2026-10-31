"""Read-only display inventory and deterministic geometry matrix. Never change system settings."""
from pathlib import Path
import ctypes as C
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src import native_api as n
from src.desktop_state import fitted_scale,clamped_position,dragged_position,EdgeDock,horizontal_clip


def main():
    n.bind(n.user,'SetProcessDpiAwarenessContext',n.W.BOOL,C.c_void_p)(C.c_void_p(-4))
    hardware=n.monitor_layout()
    cases=[]
    layouts=[(0,0,1920,1040),(-2560,-200,0,1240),(0,0,800,560),(1920,0,3000,1880)]
    for area in layouts:
        for dpi in (96,120,144,192,240,288):
            for user_scale in (.5,.75,1,1.5,2):
                scale=fitted_scale(user_scale,area,dpi)
                w=h=round(512*scale)
                x,y=clamped_position(99999,-99999,w,h,area)
                assert area[0]<=x<=area[2]-w and area[1]<=y<=area[3]-h
                for side in ('left','right'):
                    dock=EdgeDock();dock.begin(side,area,x,y,w,scale)
                    px=dock.advance(1)
                    clip=horizontal_clip(px,w,area)
                    assert 0<=clip[0]<clip[1]<=w
                cases.append({'area':area,'dpi':dpi,'user_scale':user_scale,'effective_scale':scale,'ok':True})
    adjacent=[(-1920,0,0,1080),(0,0,2560,1440)]
    assert dragged_position(-128,400,256,256,adjacent[1],adjacent)==(-128,400)
    report={'ok':True,'observed_displays':hardware,'simulated_cases':len(cases),'cases':cases,
            'mixed_dpi_hardware_observed':len({m['dpi'] for m in hardware if m['dpi']})>1,
            'physical_hotplug_tested':False,'note':'Geometry simulation does not certify a physical mixed-DPI/hotplug matrix.'}
    path=ROOT/'runtime/display-validation-v0.7.json';path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
