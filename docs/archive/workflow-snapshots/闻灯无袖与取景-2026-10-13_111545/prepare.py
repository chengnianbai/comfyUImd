"""Prepare and validate this authorized prompt-only, single-front experiment."""
import copy
import hashlib
import json
from pathlib import Path
import ssl
import sys
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / 'task_config.json').read_text(encoding='utf-8'))
ROOT = Path(CFG['root'])
BASE = CFG['base']
sys.path.insert(0, str(ROOT / '_scripts'))
from diff_wf import compare_state, render_report
from relayout_wendeng import intersections

def record(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

original = json.loads((HERE / 'local_before.json').read_text(encoding='utf-8'))
assert (HERE / 'local_before.json').read_bytes() == (HERE / 'remote_before.json').read_bytes()
candidate = copy.deepcopy(original)
nodes = {n['id']: n for n in candidate['nodes']}
nodes[1313]['widgets_values'][0] = (
    'Full-length front-view studio reference photograph of the same young East Asian man as the supplied face reference. '
    'Preserve his exact facial identity, facial structure and proportions, eyes, eyebrows, nose, lips, chin and jawline, '
    'apparent age, messy wavy black hair, hairline and small mole by the outer eye. '
    'He wears a plain white fitted sleeveless crew-neck T-shirt with no sleeves, no logo or pattern. '
    'The entire shirt hem is neatly tucked inside the waistband of plain white mid-thigh shorts. '
    'The waistband is clearly visible and the shirt does not hang over the shorts. No jacket or accessories. Bare feet. '
    'His barefoot standing height is 183 cm. A tall, lean athletic male fashion-model physique, naturally long arms and legs, '
    'narrow waist, natural moderate shoulder width and a subtle V-shaped torso. Near eight-head body proportions, '
    'with a naturally proportioned head and anatomically natural torso. '
    'His exposed shoulders have smoothly rounded, moderately developed deltoids, with clear front and outer shoulder contours. '
    'The upper arms are moderately full, with natural biceps volume and a visible gentle transition between shoulder and upper arm. '
    'The legs are long and lean, with subtle thigh muscle contours, naturally shaped calves and slim ankles. '
    'Healthy realistic muscle volume, not bulky or extremely thin, no exaggerated bodybuilding definition. '
    'Face and body directly forward, head upright, eye line horizontal, shoulders level. '
    'Stand naturally straight, arms relaxed slightly clear of the waist, both feet flat on the same level floor, no raised foot. '
    'Use a wider full-length framing from a comfortable camera distance, natural 70 mm portrait perspective, '
    'camera level around mid-torso, straight-on without tilt or wide-angle distortion. '
    'The entire figure from hair to bare soles occupies about 85 percent of the image height. '
    'Leave generous white space above the head and visible floor below both feet; do not crop head, hands or feet. '
    'Centered on a pure white seamless studio background, soft even lighting revealing natural shoulder and arm form, '
    'realistic skin texture, unified photographic rendering.'
)
nodes[1313]['title'] = '正面身体指令 · 无袖扎腰 / 肩臂 / 85%取景（待验收）'
for nid in (1333, 1353):
    old = nodes[nid]['widgets_values'][0]
    assert 'plain white crew-neck T-shirt' in old
    nodes[nid]['widgets_values'][0] = old.replace(
        'plain white crew-neck T-shirt',
        'plain white sleeveless crew-neck T-shirt neatly tucked fully into the shorts waistband'
    ) + (
        ' Preserve the front view\'s moderately developed rounded shoulders, natural upper-arm muscle volume, '
        'lean thighs and calves, visible shorts waistband and wider framing with the entire figure occupying '
        'about 85 percent of image height. Keep the full head and both feet visible.'
    )
nodes[1373]['widgets_values'][0] = (
    '主工作入口：闻灯.json；仍待用户验收。\n'
    '完整主图保留正面、侧面、背面；本轮验证只提交正面一张。\n\n'
    '正面脸部母版00017；侧面保留00009及正面身体参考。\n'
    '目标：183 cm修长男性模特体型，适度圆润肩臂肌肉、精瘦腿部；白色无袖T恤全部扎进白短裤。\n'
    '取景目标：人物约占画面高度85%，头顶和双脚下方留白，完整头脚，双脚落地。\n'
    '两张新参考只用于分析服装/肌肉，没有接入图像条件，不借用参考人物的脸。\n'
    '节点1024标题与实际选项不符：当前实际选择FLUX1/flux1-schnell.safetensors；本轮未切换模型。\n'
    '每轮生成后先展示实际图片与不足，等待用户决定下一轮，不自动继续生成。\n'
    '旧P分段缩放不采用；侧面角度和身份仍待解决。'
)

assert candidate['links'] == original['links']
assert candidate['groups'] == original['groups']
for before, after in zip(original['nodes'], candidate['nodes']):
    if before['id'] not in (1313, 1333, 1353, 1373):
        assert before == after, before['id']
    else:
        b, a = copy.deepcopy(before), copy.deepcopy(after)
        for field in ('widgets_values', 'title'):
            b.pop(field, None)
            a.pop(field, None)
        assert b == a, before['id']
assert not intersections(candidate['nodes'])
record('candidate.json', candidate)
report = compare_state(CFG['state'], HERE / 'candidate.json')
record('delta_review.json', report)
print(render_report(report), flush=True)

def dependencies(api, ids):
    found = set()
    def walk(key):
        if key in found:
            return
        found.add(key)
        assert api[key]['class_type'], key
        for value in api[key]['inputs'].values():
            if isinstance(value, list) and len(value) == 2 and str(value[0]) in api:
                walk(str(value[0]))
    for key in ids:
        walk(key)
    return {key: node for key, node in api.items() if key in found}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 2200, 'height': 1500}, ignore_https_errors=True)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until='networkidle', timeout=60000)
    page.wait_for_function('()=>!!window.comfyAPI?.app?.app?.graph && !!window.comfyAPI?.app?.app?.canvas?.canvas', timeout=60000)
    page.wait_for_timeout(3000)
    result = page.evaluate('''async cfg => {
        const {app}=await import('/scripts/app.js');
        await app.loadGraphData(cfg.original);
        const before=(await app.graphToPrompt()).output;
        for (const id of [1313,1333,1353,1373]) {
            const n=app.graph.getNodeById(id), saved=cfg.candidate.nodes.find(n=>n.id===id);
            n.widgets[0].value=saved.widgets_values[0];
            n.title=saved.title;
        }
        const after=(await app.graphToPrompt()).output;
        app.canvas.ds.scale=.70;app.canvas.ds.offset=[70,-720];app.canvas.setDirty(true,true);
        return {before,after,nodes:app.graph._nodes.map(n=>({id:Number(n.id),pos:Array.from(n.pos),size:Array.from(n.size)})),
          missing:app.graph._nodes.filter(n=>!n.constructor.nodeData && n.type!=='Note').map(n=>n.type)};
    }''', {'original': original, 'candidate': candidate})
    active = [str(n['id']) for n in original['nodes'] if n['type'] in ('SaveImage','PreviewImage') and n.get('mode',0)==0]
    before, after = dependencies(result['before'], active), dependencies(result['after'], active)
    assert set(before) == set(after)
    changed = []
    for key in before:
        b, a = copy.deepcopy(before[key]), copy.deepcopy(after[key])
        b.pop('_meta', None); a.pop('_meta', None)
        if b != a:
            changed.append(key)
            b['inputs'].pop('text'); a['inputs'].pop('text')
            assert b == a, key
    assert set(changed) == {'1313','1333','1353'}, changed
    front = dependencies(after, ['15'])
    assert len(front)==17
    assert [key for key,n in front.items() if n['class_type']=='SaveImage']==['15']
    assert front['1316']['inputs']['seed']==20261008
    assert front['1024']['inputs']['unet_name']=='FLUX1\\flux1-schnell.safetensors'
    overlaps = intersections(result['nodes'])
    assert not overlaps, overlaps
    assert not result['missing'], result['missing']
    assert not errors, errors
    record('full_browser_api.json', after)
    record('front_browser_api.json', front)
    page.wait_for_timeout(2000)
    page.screenshot(path=str(HERE/'prepared_front_layout.png'))
    browser.close()

ctx = ssl._create_unverified_context()
filename='闻灯-脸部正面-成品_00017_.png'
query=urllib.parse.urlencode({'filename':filename,'type':'input'})
remote_face=urllib.request.urlopen(BASE+'/view?'+query,context=ctx,timeout=30).read()
local_face=(ROOT/'系列-夜市百相簿/02-角色/闻灯/设定图/已确定脸部图'/filename).read_bytes()
assert remote_face==local_face
validation={'nodes':len(candidate['nodes']),'links':len(candidate['links']),'groups':len(candidate['groups']),
 'api_changes':changed,'front_dependencies':len(front),'full_dependencies':len(after),'node_overlaps':0,
 'browser_errors':errors,'links_unchanged':True,'groups_unchanged':True,
 'face_reference_equal':True,'face_reference_sha256':hashlib.sha256(remote_face).hexdigest(),
 'reference_photos_conditioning':False,'actual_unet_file':front['1024']['inputs']['unet_name'],
 'model_title_mismatch':True,'framing_target_percent':85,'run_limit':1}
record('validation.json', validation)
print(json.dumps(validation,ensure_ascii=False),flush=True)
