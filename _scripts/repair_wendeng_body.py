"""Apply only the tested reference paths; retain historical nodes for recovery."""
import copy
import json
from pathlib import Path

from relayout_wendeng import intersections
from wf_api import build_api, deps

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'docs/archive/workflow-snapshots/闻灯恢复-2026-10-10'
EXP=ROOT/'系列-夜市百相簿/02-角色/闻灯/设定图'
wf=json.loads((OUT/'layout_saved.json').read_text(encoding='utf-8'))
by={n['id']:n for n in wf['nodes']}
original=copy.deepcopy(wf)
wf['extra'].pop('reroutes',None)
wf['extra'].pop('linkExtensions',None)

def clone(template,nid,title,pos):
    n=copy.deepcopy(by[template]);n.update(id=nid,title=title,pos=pos,mode=0)
    for s in n.get('inputs',[]):s['link']=None
    for s in n.get('outputs',[]):s['links']=[]
    wf['nodes'].append(n);by[nid]=n
    return n

def connect(src,ss,dst,ds):
    old=by[dst]['inputs'][ds].get('link')
    if old is not None:
        row=next(l for l in wf['links'] if l[0]==old)
        by[row[1]]['outputs'][row[2]]['links'].remove(old)
        wf['links'].remove(row)
    lid=max(wf['last_link_id'],*(l[0] for l in wf['links']))+1
    wf['last_link_id']=lid
    wf['links'].append([lid,src,ss,dst,ds,by[src]['outputs'][ss]['type']])
    by[dst]['inputs'][ds]['link']=lid
    by[src]['outputs'][ss].setdefault('links',[]).append(lid)

# The current front path already reproduces B. The side consumes that body first,
# followed by the complete approved profile, in the same order as experiment I.
by[1330]['widgets_values'][0]='闻灯-脸部左侧-成品_00009_.png [output]'
by[1330]['title']='已确认侧脸母版 00009（完整原图）'
by[1331]['title']='侧脸母版 · 参考归一化'
by[1332]['title']='侧脸母版 · 参考 latent'
x,y=by[1331]['pos']
clone(1331,1370,'正面全身 · 身体与服装参考',[x,y+370])
clone(1332,1371,'正面全身 · 参考 latent',[x,y+555])
x,y=by[1335]['pos']
clone(1335,1372,'加入已确认侧脸 · 双参考',[x,y+185])
by[1336]['pos'][1]=y+370
by[1335]['title']='先加入正面全身参考'
connect(1317,0,1370,0)
connect(1370,0,1371,0)
connect(1026,0,1371,1)
connect(1371,0,1335,1)
connect(1335,0,1372,0)
connect(1332,0,1372,1)
connect(1372,0,1336,1)
side_api=json.loads((EXP/'全身验证-2026-10-10/I_side_two_refs_api.json').read_text(encoding='utf-8'))
by[1333]['widgets_values'][0]=side_api['1353']['inputs']['text']
by[1333]['title']='侧面编辑指令 · 双参考（角度待验收）'
# Exact back-view edit tested in F, taking the current generated front body.
connect(1317,0,1351,0)
by[1351]['title']='正面全身 → 背面参考'
back_api=json.loads((EXP/'锁脸诊断-2026-10-09/F_back_from_body_api.json').read_text(encoding='utf-8'))
by[1353]['widgets_values'][0]=back_api['1353']['inputs']['text']
by[1353]['title']='背面编辑指令 · 保持身体与白色服装'
by[1350]['title']='旧背面输入 · 已脱离主线（停用）'
by[1350]['mode']=2
by[1350]['pos']=[8000,6800]
by[1302]['title']='全身输出尺寸 1024×1792（三视角共用）'
for nid in [1316,1336,1356]:by[nid]['title']='Kontext 参考采样 · 20步 / denoise 1.0'
for nid in [1021,1109,1111,1368]:
    by[nid]['mode']=2
    by[nid]['title']='停用 · '+('诊断裁脸（不回接全身）' if nid==1368 else '脸部历史输出')
# ImageCrop had stale ImageScale widget ports despite its changed backend type.
image_link=by[1360]['inputs'][0]['link']
by[1360]['inputs']=[{'name':'image','type':'IMAGE','link':image_link}]+[
    {'name':k,'type':'INT','widget':{'name':k},'link':None} for k in ['width','height','x','y']]
note=clone(16,1373,'当前使用说明 / 全身候选',[3100,180])
note['size']=[950,610]
note['widgets_values']=['当前点击运行：仅输出全身正面、侧面、背面候选。\n\n正面：完整已确认脸部母版 00017。\n侧面：正面全身作为身体/服装参考，同时读取已确认侧脸 00009。\n背面：沿用当前正面全身的身体/服装。\n\n白T恤＋白短裤；身份为软参考，需要逐张验收。\n当前侧面仍偏斜侧，未达到严格90°，不要直接标成三视图终稿。\n\n右侧脸部历史链与裁脸精修输出已停用，不会自动重画已确认脸。\n可在绿色分组右侧查看并保存三个全身输出。']
wf['last_node_id']=1373
for group in wf['groups'][1:]:
    if group['id']==3:
        group['bounding'][2]=4040
        group['bounding'][3]=740
    elif group['id']==5:group['bounding'][3]=850
    elif group['id']==14:group['bounding'][3]=1790
    elif group['id']==6:group['title']='04 · 全身背面 / 正面身体参考'
wf['groups'][0]['bounding'][3]=7500
assert not intersections(wf['nodes'])
# All port declarations and back-references must agree after rewiring.
for lid,src,ss,dst,ds,typ in wf['links']:
    assert by[src]['outputs'][ss]['type']==typ==by[dst]['inputs'][ds]['type'],lid
    assert by[dst]['inputs'][ds]['link']==lid,lid
    assert lid in by[src]['outputs'][ss]['links'],lid
api,_=build_api(wf)
roots=[k for k,n in api.items() if n['class_type'] in ('SaveImage','PreviewImage')]
assert set(roots)=={'14','15','316','346'},roots
needed=deps(api,roots)
assert not any(k in needed for k in ['1015','1104','1046','1034','1213','1366'])
prompt={k:v for k,v in api.items() if k in needed}
for k,n in prompt.items():
    for val in n['inputs'].values():
        if isinstance(val,list):assert val[0] in prompt,(k,val)
for nid in [1310,1313,1314,1316,1302]:
    assert by[nid]['widgets_values']==next(n for n in original['nodes'] if n['id']==nid)['widgets_values']
(OUT/'body_candidate.json').write_text(json.dumps(wf,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'body_candidate_api.json').write_text(json.dumps(prompt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'nodes':len(wf['nodes']),'links':len(wf['links']),'overlaps':0,'active_outputs':roots,'executed_nodes':len(prompt),'historical_samplers_excluded':True}))
