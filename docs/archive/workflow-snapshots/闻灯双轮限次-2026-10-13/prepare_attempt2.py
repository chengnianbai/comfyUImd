"""Prepare the last authorized attempt with unambiguous garment/framing text."""
import copy
import hashlib
import json
from pathlib import Path
import ssl
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[4]
E=Path(__file__).resolve().parent
OUT=ROOT/'系列-夜市百相簿/02-角色/闻灯/设定图/全身验证-2026-10-13'
MAIN=ROOT/'系列-夜市百相簿/02-角色/闻灯/工作流/闻灯.json'
BASE='https://gw-da074043649a46aa8485bca1ba422cbe.cn-beijing.aigclinks.com:8016'
CTX=ssl._create_unverified_context()
REF_NAME='闻灯-正脸母版00017-仅头脸裁切_验证01.png'

def record(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def get(path):
    return urllib.request.urlopen(BASE+path,context=CTX,timeout=45).read()

workflow_path='/userdata/'+urllib.parse.quote('workflows/闻灯.json',safe='')
before_bytes=MAIN.read_bytes()
assert get(workflow_path)==before_bytes,'Remote and local main workflow differ; stop'
before=json.loads(before_bytes)
record(E/'attempt2_remote_before.json',before)
queue=json.loads(get('/queue'))
record(E/'attempt2_queue_before.json',queue)
assert not queue['queue_running'] and not queue['queue_pending'],'Queue is busy; stop'
candidate=copy.deepcopy(before)
nodes={n['id']:n for n in candidate['nodes']}
assert nodes[1310]['widgets_values'][0]==REF_NAME

nodes[1313]['widgets_values'][0]=( 
    'Wide long-shot full-length studio photograph in a vertical 9:16 frame. The complete person is deliberately shown '
    'smaller and farther from the camera than in a close portrait: hair-to-sole height is about 72 percent of the image, '
    'with broad clean white margins above the hair and below the bare feet and visible white background on both sides. '
    'Camera straight-on at mid-torso level with natural perspective; no close-up, no medium shot, no crop. '
    'The same young East Asian man as the supplied face-only reference. Preserve his recognizable identity, same face shape, '
    'eyes, brows, nose, lips, jaw, apparent age, messy wavy black hairstyle and hairline. '
    'He wears a plain white cotton sleeveless muscle tee: a crew-neck tank top with broad shoulder straps and large armholes. '
    'Both shoulders are fully bare from the neck to the shoulder joints; no sleeves, no short sleeves, and no fabric over the deltoids. '
    'The fitted top ends at the waist and is tucked completely inside the shorts; the white shorts waistband is clearly visible, '
    'with no shirt hanging over it. Plain white mid-thigh shorts, barefoot, no accessories. '
    'His barefoot standing height is 183 cm. Tall lean male fashion-model proportions, naturally long legs and arms, '
    'long legs relative to the torso, narrow waist, natural moderate shoulder width, near eight heads tall. '
    'Lean athletic body with rounded moderately developed deltoids, visible natural biceps and triceps contours, '
    'slim thighs with subtle athletic definition and naturally shaped calves; healthy realistic muscle volume, not a bodybuilder. '
    'Stand directly facing the camera, head upright, shoulders level, arms relaxed slightly away from the torso so the bare shoulders '
    'and upper arms are visible. Both legs straight, both bare feet flat on the same floor, weight evenly distributed. '
    'Pure white seamless studio, soft even lighting, realistic photographic skin and fabric, consistent face and body rendering.'
)
nodes[1313]['title']='正面身体指令 · 无袖背心 / 扎腰 / 72%远景（最终限次验证）'
for nid in (1333,1353):
    text=nodes[nid]['widgets_values'][0]
    text=text.replace('plain white sleeveless crew-neck T-shirt neatly tucked fully into the shorts waistband',
                      'plain white sleeveless tank top with broad straps, both shoulders bare, tucked completely inside the white shorts waistband')
    text=text.replace('plain white sleeveless crew-neck T-shirt and plain white shorts',
                      'plain white sleeveless tank top with broad straps tucked completely inside the white shorts waistband, and plain white shorts')
    nodes[nid]['widgets_values'][0]=text
nodes[1373]['widgets_values'][0]=(
    '主工作入口：闻灯.json，尚待用户验收。\n'
    '本次限次验证最多两轮，第一轮头脸参考裁切无效；本轮为第2轮、最后一轮。完成后停止并交用户判断。\n'
    '正脸输入为已确认00017的头脸像素裁切，原母版不变。\n'
    '第二轮只强化服装/取景措辞：白色宽肩带背心式无袖上衣、裸露双肩、完全扎入白短裤；全身高度约72%、上下留白。\n'
    '183 cm修长男模比例、自然肩臂和腿部肌肉，双脚落地。\n'
    'seed、KSampler、模型引用、采样、分辨率及计算连线不变。只提交正面一张。\n'
    '模型文件别名的大小与官方Kontext fp8_scaled相同；当前服务未暴露完整张量头/SHA，内容身份仍待验证。\n'
    '每轮图像生成后发图并由用户判断的临时规则，在本次限次任务结束后恢复。'
)

assert candidate['links']==before['links'] and candidate['groups']==before['groups']
changed_nodes=[a['id'] for a,b in zip(before['nodes'],candidate['nodes']) if a!=b]
assert changed_nodes==[1313,1333,1353,1373],changed_nodes
(E/'attempt2_candidate.json').write_text(json.dumps(candidate,ensure_ascii=False,indent=2),encoding='utf-8')
record(E/'attempt2_delta.json',{'baseline_sha256':hashlib.sha256(before_bytes).hexdigest(),
 'candidate_sha256':hashlib.sha256((E/'attempt2_candidate.json').read_bytes()).hexdigest(),
 'changed_nodes':changed_nodes,'links_unchanged':True,'groups_unchanged':True,
 'unrelated_node_1002_dangling_link_preserved':True,
 'attempt_number':2,'attempt_limit':2})

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':2200,'height':1500},ignore_https_errors=True)
    errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
    page.goto(BASE,wait_until='networkidle',timeout=60000)
    page.wait_for_function('()=>!!window.comfyAPI?.app?.app?.graph && !!window.comfyAPI?.app?.app?.canvas?.canvas',timeout=60000)
    page.wait_for_timeout(2500)
    result=page.evaluate('''async wf=>{
      const {app}=await import('/scripts/app.js');await app.loadGraphData(wf);
      const api=(await app.graphToPrompt()).output;
      app.canvas.ds.scale=.70;app.canvas.ds.offset=[70,-720];app.canvas.setDirty(true,true);
      return {api,nodes:app.graph._nodes.map(n=>({id:Number(n.id),pos:Array.from(n.pos),size:Array.from(n.size)})),
        missing:app.graph._nodes.filter(n=>!n.constructor.nodeData && n.type!=='Note').map(n=>n.type),
        ref:app.graph.getNodeById(1310).widgets[0].value};
    }''',candidate)
    assert result['ref']==REF_NAME
    active=set()
    def visit(key):
        if key in active:return
        active.add(key)
        for val in result['api'][key]['inputs'].values():
            if isinstance(val,list) and len(val)==2 and str(val[0]) in result['api']:visit(str(val[0]))
    visit('15')
    front={k:v for k,v in result['api'].items() if k in active}
    assert len(front)==17,(len(front),list(front))
    assert front['1310']['inputs']['image']==REF_NAME
    assert front['1316']['inputs']['seed']==20261008
    assert front['1316']['inputs']['steps']==20 and front['1316']['inputs']['cfg']==1
    old=json.loads((E/'attempt1_front_api.json').read_text(encoding='utf-8'))
    changed=[]
    for key in set(old)|set(front):
        a,b=copy.deepcopy(old.get(key)),copy.deepcopy(front.get(key))
        if key=='15' and a and b:
            a['inputs']['filename_prefix']=b['inputs']['filename_prefix']='<normalized>'
        if a!=b:changed.append(key)
    assert set(changed)=={'1313'},changed
    assert not result['missing'],result['missing']
    import sys
    sys.path.insert(0,str(ROOT/'_scripts'))
    from relayout_wendeng import intersections
    overlap=intersections(result['nodes']);assert not overlap,overlap
    assert not errors,errors
    record(E/'attempt2_front_api.json',front)
    page.screenshot(path=str(E/'attempt2_layout.png'))
    browser.close()
record(E/'attempt2_validation.json',{'changed_nodes':changed_nodes,'changed_front_api_nodes':changed,
 'front_dependencies':len(front),'seed':20261008,'steps':20,'cfg':1,'links_unchanged':True,
 'groups_unchanged':True,'node_overlaps':0,'browser_errors':errors,
 'reference_crop_persisted':True,'generation_attempt':2,'generation_limit':2})
print(json.dumps({'attempt':2,'changed_nodes':changed_nodes,'front_dependencies':len(front),
 'changed_front_api_nodes':changed,'node_overlaps':0},ensure_ascii=False),flush=True)
