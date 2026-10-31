# -*- coding: utf-8 -*-
"""气泡文案池（随机闲聊 + 点击反馈台词）。

时间感知（P1-4）：白天/深夜分开闲聊文案；打盹文案（P2-9）。
"""
import random
import json
from .native_model import ROOT

with (ROOT / "assets/companion.json").open(encoding="utf-8") as _file:
    CONTENT = json.load(_file)


def line(event):
    return random.choice(CONTENT[event])

IDLE_LINES = [          # 白天闲聊
    "今天也要好好学习哦~",
    "作业写完了吗？(歪头)",
    "我眼镜是不是该擦了…",
    "桌面要记得整理啦！",
    "诶嘿~ 摸鱼真开心",
    "肚子有点饿了…",
    "要不要一起学习？",
]

IDLE_LINES_NIGHT = [    # 深夜闲聊（23:00–6:00）
    "夜深了，该睡觉啦…",
    "呼…好困…",
    "熬夜对身体不好哦",
    "晚安，明天见~",
    "(打了个哈欠)",
]

DROWSY_LINES = [        # 闲置打盹提示
    "(打盹…Zzz)",
    "(眯着眼睛打瞌睡…)",
    "(头一点一点的…)",
]

HEAD_LINES = [
    "呜…别摸我头啦！(脸红)",
    "头发会乱的啦！",
    "呜哇！不要突然戳我！",
]

BODY_LINES = [
    "诶？你在看什么？",
    "我身上有什么奇怪的东西吗…",
    "哼！我才没有偷懒！",
    "干嘛啦！吓我一跳！",
]


def idle_lines():
    """按当前时间返回合适的闲聊池。"""
    import time
    h = time.localtime().tm_hour
    if h >= 23 or h < 6:
        return CONTENT["night"]
    return CONTENT["idle"]


def random_idle():
    return random.choice(idle_lines())
