"""Build an offline preview from the same frame manifest as the desktop app."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def main():
    meta = json.loads((ROOT / "assets/frame_meta.json").read_text(encoding="utf-8"))
    def clip(action):
        spec = meta[action]
        names = spec.get("frame_files") or [p.relative_to(ROOT / "assets").as_posix() for p in sorted((ROOT / "assets" / action).glob(f"{action}_*.png"))]
        times = spec.get("frame_durations_ms", [spec["duration_ms"]] * len(names))
        return [{"url": "../assets/" + name, "ms": duration} for name, duration in zip(names, times)]
    cards = [
        {"label": "扶眼镜 · 开始专注", "frames": clip("adjustGlasses")},
        {"label": "坐下 → 打盹 → 站起", "frames": clip("sleepEnter") + clip("sleep")[2:] + clip("sleepExit")},
        {"label": "起步 → 左右脚交替 → 停步", "frames": clip("walkEnter") + clip("walk") + clip("walkExit")},
        {"label": "拖动 · 慢速侧身跑动", "frames": clip("dragRun")},
        {"label": "屏幕边缘 · 探头", "frames": clip("peek")},
        *[{"label": label, "frames": clip(action)} for action, label in (("idle", "待机"), ("headClick", "摸头回应"), ("bodyClick", "身体互动"), ("happy", "开心动作"))],
    ]
    path = ROOT / "docs/动画预览.html"
    old = path.read_text(encoding="utf-8")
    shell = old[:old.index("<script>")]
    shell = shell.replace("六组动作均由 GPT 参考原图重绘。", "v0.4：新增扶眼镜与睡眠过渡，走路重绘仍待验收。")
    shell = shell.replace("v0.4：新增扶眼镜与睡眠过渡，走路重绘仍待验收。", "v0.5：悬空拖动、边缘探头和左右脚交替步态。")
    shell = shell.replace("v0.5：悬空拖动、边缘探头和左右脚交替步态。", "v0.7：八帧侧身跑动，680ms 周期，探头注视使用者。")
    shell = shell.replace("六个关键姿态之间", "关键姿态之间")
    script = r'''<script>
const cards=__CARDS__;let playing=true,previous=performance.now(),speed=1;const players=[];
for(const card of cards){const element=document.createElement('article');element.className='card';element.innerHTML=`<h2>${card.label}</h2><div class="stage"><img alt="${card.label}"></div><footer><input type="range" min="0" max="${card.frames.length-1}" value="0" aria-label="逐帧预览"><span class="frame"></span></footer>`;document.querySelector('#grid').append(element);const p={frames:card.frames,index:0,elapsed:0,img:element.querySelector('img'),slider:element.querySelector('input'),counter:element.querySelector('.frame')};p.paint=()=>{p.img.src=p.frames[p.index].url;p.slider.value=p.index;p.counter.textContent=`${p.index+1} / ${p.frames.length}`;};p.paint();p.slider.oninput=()=>{playing=false;document.querySelector('#play').textContent='继续播放';p.index=+p.slider.value;p.elapsed=0;p.paint();};for(const f of card.frames){const image=new Image();image.src=f.url;}players.push(p);}
document.querySelector('#play').onclick=e=>{playing=!playing;e.target.textContent=playing?'暂停播放':'继续播放';};document.querySelector('#background').onclick=e=>{document.body.classList.toggle('dark');e.target.textContent=document.body.classList.contains('dark')?'浅色背景':'深色背景';};document.querySelector('#speed').onchange=e=>{speed=+e.target.value;};function tick(now){const dt=Math.min(250,now-previous)*speed;previous=now;if(playing)for(const p of players){p.elapsed+=dt;while(p.elapsed>=p.frames[p.index].ms){p.elapsed-=p.frames[p.index].ms;p.index=(p.index+1)%p.frames.length;p.paint();}}requestAnimationFrame(tick);}requestAnimationFrame(tick);
</script></html>'''
    path.write_text(shell + script.replace("__CARDS__", json.dumps(cards, ensure_ascii=False)), encoding="utf-8")
    print("Updated offline preview from the runtime manifest.")


if __name__ == "__main__":
    main()
