"""Arrange the existing Wengdeng graph without changing execution data."""
import copy
import json
from pathlib import Path
import sys

from wf_api import build_api


def size(node):
    value = node.get('size', [350, 100])
    return list(value) if not isinstance(value, dict) else [value['0'], value['1']]


def intersections(nodes):
    pairs = []
    for i, a in enumerate(nodes):
        ax, ay = a['pos']; aw, ah = size(a)
        for b in nodes[i + 1:]:
            bx, by = b['pos']; bw, bh = size(b)
            if ax < bx + bw and bx < ax + aw and ay - 34 < by + bh and by - 34 < ay + ah:
                pairs.append([a['id'], b['id']])
    return pairs


def arrange(original):
    wf = copy.deepcopy(original)
    by = {n['id']: n for n in wf['nodes']}
    used = set()
    groups = []
    for n in wf['nodes']:
        w, h = size(n)
        if n['type'] in ('SaveImage', 'PreviewImage', 'LoadImage'):
            w, h = max(w, 440), max(h, 560)
        elif n['type'] == 'CLIPTextEncode':
            w, h = max(w, 640), max(h, 220)
        elif n['type'] == 'KSampler':
            w, h = max(w, 400), max(h, 310)
        else:
            w, h = max(w, 350), max(h, 100)
        n['size'] = [round(w), round(h)]

    def group(title, ids, color):
        ns = [by[i] for i in ids]
        x = min(n['pos'][0] for n in ns) - 35
        y = min(n['pos'][1] for n in ns) - 95
        r = max(n['pos'][0] + size(n)[0] for n in ns) + 35
        b = max(n['pos'][1] + size(n)[1] for n in ns) + 35
        groups.append({'id': 3 + len(groups), 'title': title, 'bounding': [x, y, r-x, b-y], 'color': color, 'font_size': 28, 'flags': {}})

    def put(nid, x, y):
        assert nid not in used, nid
        used.add(nid)
        by[nid]['pos'] = [x, y]

    def columns(title, cols, x, y, color='#506779'):
        ids = []
        for col in cols:
            cy = y
            for nid in col:
                put(nid, x, cy)
                ids.append(nid)
                cy += size(by[nid])[1] + 85
            x += max(size(by[i])[0] for i in col) + 85
        group(title, ids, color)

    columns('01 · 共享模型 / 编码器 / 全身尺寸',
            [[1024,1026],[1025,1030],[1302],[1002,1003],[1018]], 80, 180, '#426c91')

    for start, y, label, upscale, scale, output in [
        (1310,1000,'02 · 全身正面 / 完整脸部母版',23,24,15),
        (1330,2050,'03 · 全身侧面 / 待复核',311,312,316),
        (1350,3100,'04 · 全身背面 / 待复核',341,342,346),
    ]:
        cols = [[start],[start+1,start+2],[start+3,start+4],[start+5,start+6],
                [start+7,upscale],[scale],[output]]
        if start == 1310:
            cols[-2].append(14)
        columns(label, cols, 80, y, '#387d76')

    columns('05 · 裁脸精修 / 独立输出，未回接全身',
            [[1360,1361,1362,1363],[1364,1365],[1366,1367],[1368]],80,4250,'#9a7544')

    columns('06 · 脸部历史链 / SDXL 正面底稿',
            [[1004,1005,1006],[1007,1008,1009],[1010,1011,1012],[1013,1014],[1015,1016],[1019,1020]],4400,180)
    columns('07 · 脸部历史链 / Kontext 正面处理',
            [[1028,1029],[1220,1221],[1045,1046],[1047,1021],[1049,1050]],4400,1350)
    columns('08 · 脸部历史链 / Kontext 转侧面',
            [[1052],[1031,1032],[1033,1034],[1035,1051]],4400,2450)
    columns('09 · 脸部历史链 / SDXL 侧面处理',
            [[1100,1101],[1102,1103],[1104,1105],[1107,1108]],4400,3400)
    columns('10 · 脸部历史链 / 侧面质感及左右输出',
            [[1210,1211],[1200,1201],[1212,1213],[1214,1109],[1110,1111]],4400,4450)

    columns('11 · 旧全身 SDXL 条件 / 停用采样支路',
            [[2,300,330],[3,5,18,19],[4,301,331,20,21],[25,12,13],[313,314,315],[343,344,345]],80,5700,'#665b62')
    columns('12 · 历史说明 / 不作为当前操作步骤',
            [[1001,16],[1023,1022],[1043,1044]],4400,5700,'#665b62')

    assert used == set(by), {'unplaced': sorted(set(by)-used)}
    overlaps = intersections(wf['nodes'])
    assert not overlaps, overlaps
    for i, a in enumerate(groups):
        ax, ay, aw, ah = a['bounding']
        for b in groups[i+1:]:
            bx, by_, bw, bh = b['bounding']
            assert not (ax < bx+bw and bx < ax+aw and ay < by_+bh and by_ < ay+ah), (a['title'],b['title'])
    minx=min(g['bounding'][0] for g in groups)-60
    miny=min(g['bounding'][1] for g in groups)-120
    maxx=max(g['bounding'][0]+g['bounding'][2] for g in groups)+60
    maxy=max(g['bounding'][1]+g['bounding'][3] for g in groups)+60
    parent=copy.deepcopy(original['groups'][0])
    parent.update(bounding=[minx,miny,maxx-minx,maxy-miny],font_size=38)
    wf['groups']=[parent]+groups
    wf.setdefault('extra',{})['ds']={'scale':0.40,'offset':[0,-780]}
    for n in wf['nodes']:
        before=next(o for o in original['nodes'] if o['id']==n['id'])
        assert {k:v for k,v in n.items() if k not in ('pos','size')} == {k:v for k,v in before.items() if k not in ('pos','size')}
    assert build_api(wf)[0] == build_api(original)[0]
    assert wf['links'] == original['links']
    return wf, {'nodes':len(by),'links':len(wf['links']),'overlaps_before':len(intersections(original['nodes'])),
                'overlaps_after':len(overlaps),'execution_unchanged':True,'groups':len(wf['groups'])}


if __name__ == '__main__':
    source,target=map(Path,sys.argv[1:3])
    wf,report=arrange(json.loads(source.read_text(encoding='utf-8-sig')))
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(wf,ensure_ascii=False,indent=2),encoding='utf-8')
    target.with_suffix('.validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
