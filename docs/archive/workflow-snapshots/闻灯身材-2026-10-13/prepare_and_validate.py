"""Validate a prompt-only change to the existing character workflow."""
import copy
import hashlib
import json
import os
from pathlib import Path
import ssl
import sys
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / '_scripts'))
from relayout_wendeng import intersections

OUT = Path(__file__).resolve().parent
BASE = os.environ['COMFY_BASE'].rstrip('/')
CTX = ssl._create_unverified_context()
original = json.loads((OUT / 'remote_before.json').read_text(encoding='utf-8'))
candidate = copy.deepcopy(original)
nodes = {n['id']: n for n in candidate['nodes']}

text = nodes[1313]['widgets_values'][0]
start = text.index('Refined slender athletic male body proportions')
end = text.index('Full body visible from head to feet', start)
body = (
    'His barefoot standing height is 183 cm. He has a tall, lean male fashion-model physique: '
    'a slender elongated silhouette, naturally long legs and long arms, a narrow waist, '
    'natural moderate shoulder width and a subtle V-shaped torso. '
    'Approximately eight anatomical head lengths from the top of the skull to the soles of the feet, '
    'with a naturally proportioned head; preserve the reference facial proportions. '
    'The legs are visually long relative to the torso. Keep the torso anatomically natural, '
    'without compressing the chest, abdomen or arms. '
    'Keep the chest and shoulders lean, with restrained muscle definition and realistic healthy body volume. '
    'Avoid a stocky build, thick waist, bulky chest, bodybuilder muscles, extreme thinness, '
    'oversized head, shortened legs or exaggerated anatomy. '
)
nodes[1313]['widgets_values'][0] = text[:start] + body + text[end:]
nodes[1313]['widgets_values'][0] = nodes[1313]['widgets_values'][0].replace(
    'weight evenly distributed on both feet, feet fully visible',
    'weight evenly distributed on both feet, both legs naturally straight, '
    'both bare feet flat on the same level floor, no raised foot, feet fully visible')
nodes[1313]['title'] = '正面身体指令 · 183 cm / 修长模特体型（待验收）'
for nid in (1333, 1353):
    nodes[nid]['widgets_values'][0] += (
        ' His barefoot standing height remains 183 cm. Preserve the tall, lean fashion-model '
        'proportions established in the front view: the same head-to-body ratio, long limbs, '
        'moderate shoulder width and narrow waist. Both bare feet rest flat on the same level floor.'
    )
nodes[1333]['title'] = '侧面身体指令 · 保持正面 183 cm 比例（角度待验收）'
nodes[1353]['title'] = '背面身体指令 · 保持正面 183 cm 比例'
nodes[1373]['widgets_values'][0] += (
    '\n\n2026-10-13：身体目标 183 cm、修长男性模特体型；只参考身体，不替换闻灯脸部。'
    '\n本轮仅改 1313/1333/1353 的身体描述，先单独验证正面。'
    '\n人物照片目前仅用于讨论体型，没有接入图像条件，也不复制抬脚姿势。'
    '\n旧 P 分段拉伸效果未获认可，不采用。当前仍是软身份参考，生成图需检查脸与身材。'
)

assert candidate['links'] == original['links']
assert candidate['groups'] == original['groups']
for before, after in zip(original['nodes'], candidate['nodes']):
    if before['id'] not in (1313, 1333, 1353, 1373):
        assert before == after, before['id']
    else:
        b, a = copy.deepcopy(before), copy.deepcopy(after)
        for key in ('widgets_values', 'title'):
            b.pop(key, None)
            a.pop(key, None)
        assert b == a, before['id']
assert not intersections(candidate['nodes'])
(OUT / 'candidate.json').write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding='utf-8')

validation = {'changed_prompt_nodes': [1313, 1333, 1353], 'height_cm': 183,
              'links_unchanged': True, 'groups_unchanged': True, 'body_photo_conditioning': False}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 2200, 'height': 1500}, ignore_https_errors=True)
    errors = []
    page.on('pageerror', lambda err: errors.append(str(err)))
    page.goto(BASE, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_function('()=>!!window.comfyAPI?.app?.app?.graph && !!window.comfyAPI?.app?.app?.canvas?.canvas', timeout=60000)
    result = page.evaluate('''async cfg => {
        const {app} = await import('/scripts/app.js');
        await app.loadGraphData(cfg.original);
        const before=(await app.graphToPrompt()).output;
        for(const id of [1313,1333,1353,1373]){
            const saved=cfg.candidate.nodes.find(n=>n.id===id),node=app.graph.getNodeById(id);
            node.widgets[0].value=saved.widgets_values[0];
            node.title=saved.title;
        }
        const after=(await app.graphToPrompt()).output;
        return {before, after, missing:app.graph._nodes.filter(n=>!n.constructor.nodeData && n.type!=='Note').map(n=>n.type),
            nodes:app.graph._nodes.map(n=>({id:Number(n.id),pos:Array.from(n.pos),size:Array.from(n.size)}))};
    }''', {'original': original, 'candidate': candidate})
    # This frontend exports unconnected notes too. Keep only active output dependencies.
    active_outputs = [str(n['id']) for n in original['nodes']
                      if n['type'] in ('SaveImage', 'PreviewImage') and n.get('mode', 0) == 0]
    def dependencies(api, output_ids):
        found = set()
        def walk(key):
            if key in found:
                return
            found.add(key)
            assert api[key]['class_type'], ('Missing class type', key)
            for value in api[key]['inputs'].values():
                if isinstance(value, list) and len(value) == 2 and str(value[0]) in api:
                    walk(str(value[0]))
        for key in output_ids:
            walk(key)
        return {key: value for key, value in api.items() if key in found}
    result['before'] = dependencies(result['before'], active_outputs)
    result['after'] = dependencies(result['after'], active_outputs)
    assert set(result['before']) == set(result['after'])
    (OUT / 'debug_browser_export.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    changed = []
    for key in result['before']:
        before = copy.deepcopy(result['before'][key])
        after = copy.deepcopy(result['after'][key])
        before.pop('_meta', None)
        after.pop('_meta', None)
        if before != after:
            changed.append(key)
            b, a = before, after
            b['inputs'].pop('text')
            a['inputs'].pop('text')
            b.pop('_meta', None)
            a.pop('_meta', None)
            assert b == a, key
    assert set(changed) == {'1313', '1333', '1353'}, changed
    assert not intersections(result['nodes']), intersections(result['nodes'])
    (OUT / 'full_browser_api.json').write_text(json.dumps(result['after'], ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'baseline_browser_api.json').write_text(json.dumps(result['before'], ensure_ascii=False, indent=2), encoding='utf-8')
    api = result['after']
    required = set()
    def visit(key):
        if key in required:
            return
        required.add(key)
        for value in api[key]['inputs'].values():
            if isinstance(value, list) and len(value) == 2 and str(value[0]) in api:
                visit(str(value[0]))
    visit('15')
    front = {key: value for key, value in api.items() if key in required}
    assert [k for k, v in front.items() if v['class_type'] == 'SaveImage'] == ['15']
    assert not {'1336', '1356', '1366', '1005', '1046'} & required
    assert front['1316']['inputs']['seed'] == 20261008
    (OUT / 'front_browser_api.json').write_text(json.dumps(front, ensure_ascii=False, indent=2), encoding='utf-8')
    page.evaluate('''async()=>{const {app}=await import('/scripts/app.js');
        app.canvas.ds.scale=.70;app.canvas.ds.offset=[70,-720];app.canvas.setDirty(true,true)}''')
    page.screenshot(path=str(OUT / 'front_layout.png'))
    validation.update(nodes=len(result['nodes']), links=len(candidate['links']),
                      groups=len(candidate['groups']), node_overlaps=0, front_dependencies=len(front),
                      full_dependencies=len(api), api_changes=changed, browser_errors=errors)
    browser.close()

# Check both fixed face sources; never overwrite the remote assets.
references = []
for nid, filename, image_type in [(1310, '闻灯-脸部正面-成品_00017_.png', 'input'),
                                 (1330, '闻灯-脸部左侧-成品_00009_.png', 'output')]:
    path = '/view?' + urllib.parse.urlencode({'filename': filename, 'type': image_type})
    remote = urllib.request.urlopen(BASE + path, context=CTX, timeout=40).read()
    local = (ROOT / '系列-夜市百相簿/02-角色/闻灯/设定图/已确定脸部图' / filename).read_bytes()
    assert remote == local, 'Face asset differs: ' + filename
    references.append({'node': nid, 'filename': filename, 'type': image_type,
                       'sha256': hashlib.sha256(remote).hexdigest(), 'byte_equal': True})
validation['face_references'] = references
(OUT / 'validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(validation, ensure_ascii=False), flush=True)
