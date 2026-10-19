# -*- coding: utf-8 -*-
"""列出所有工作流文件里的正向提示词，确认用户看到的是哪一份"""
import os, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

WF = r'D:\xiaobai-claude code\ComfyUI\user\default\workflows'

def brief(s, n=120):
    s = (s or '').replace('\n', ' ')
    return s[:n] + ('...' if len(s) > n else '')

for f in sorted(os.listdir(WF)):
    if not f.endswith('.json'):
        continue
    p = os.path.join(WF, f)
    print('=' * 78)
    print('FILE :', f, '  %.1f KB' % (os.path.getsize(p) / 1024))
    try:
        d = json.load(open(p, encoding='utf-8'))
    except Exception as e:
        print('  !! 解析失败', e)
        continue
    nodes = d.get('nodes', [])
    for n in nodes:
        t = n.get('type')
        if t in ('CLIPTextEncode', 'CheckpointLoaderSimple', 'KSampler', 'EmptyLatentImage', 'LatentUpscale'):
            title = n.get('title', '')
            wv = n.get('widgets_values', [])
            print('  [%s] %s' % (t, title))
            for v in wv:
                if isinstance(v, str):
                    print('      ->', brief(v))
                else:
                    print('      ->', v)
    # 显示工作流内的 note
    wfid = d.get('id')
    print('  workflow id:', wfid)
