"""Build one face-only reference variant and validate its prompt path."""
import copy
import hashlib
import json
from pathlib import Path
import ssl
import urllib.parse
import urllib.error
import urllib.request
import uuid

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = Path(__file__).resolve().parent
OUTPUT = ROOT / '系列-夜市百相簿/02-角色/闻灯/设定图/全身验证-2026-10-13'
WORKFLOW = ROOT / '系列-夜市百相簿/02-角色/闻灯/工作流/闻灯.json'
FACE = ROOT / '系列-夜市百相簿/02-角色/闻灯/设定图/已确定脸部图/闻灯-脸部正面-成品_00017_.png'
REF_DIR = ROOT / '系列-夜市百相簿/02-角色/闻灯/工作流/参考素材'
REF_NAME = '闻灯-正脸母版00017-仅头脸裁切_验证01.png'
REF_LOCAL = REF_DIR / REF_NAME
BASE = 'https://gw-da074043649a46aa8485bca1ba422cbe.cn-beijing.aigclinks.com:8016'
CTX = ssl._create_unverified_context()

def record(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def request(path, data=None, headers=None):
    req = urllib.request.Request(BASE + path, data=data, headers=headers or {})
    return urllib.request.urlopen(req, context=CTX, timeout=45).read()

remote_path = '/userdata/' + urllib.parse.quote('workflows/闻灯.json', safe='')
local_before = WORKFLOW.read_bytes()
remote_before = request(remote_path)
assert remote_before == local_before, 'Remote and local main workflow differ; stop'
record(EVIDENCE / 'remote_before.json', json.loads(remote_before))
record(EVIDENCE / 'queue_before.json', json.loads(request('/queue')))
queue = json.loads((EVIDENCE / 'queue_before.json').read_text(encoding='utf-8'))
assert not queue['queue_running'] and not queue['queue_pending'], 'Queue is busy; stop'

# Preserve the complete head and face as original pixels; remove shoulders/clothes.
master = Image.open(FACE).convert('RGB')
assert master.width == 880 and master.height == 1184, master.size
crop = master.crop((0, 0, master.width, master.width))
assert crop.size == (880, 880)
crop.save(REF_LOCAL, format='PNG', optimize=False)
reopened = Image.open(REF_LOCAL).convert('RGB')
assert list(reopened.getdata()) == list(crop.getdata())
assert list(reopened.getdata()) == list(master.crop((0, 0, master.width, master.width)).getdata())

# Upload under a new filename; do not replace the confirmed original.
ref_url = '/view?' + urllib.parse.urlencode({'filename': REF_NAME, 'type': 'input'})
try:
    remote_ref = request(ref_url)
    assert remote_ref == REF_LOCAL.read_bytes(), 'Existing uploaded reference differs'
    response = {'name': REF_NAME, 'subfolder': '', 'type': 'input', 'reused_after_byte_readback': True}
except urllib.error.HTTPError as error:
    if error.code != 404:
        raise
    boundary = '----Codex' + uuid.uuid4().hex
    parts = []
    for key, value in (('overwrite', 'false'), ('type', 'input'), ('subfolder', '')):
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{REF_NAME}"\r\nContent-Type: image/png\r\n\r\n'.encode())
    parts.append(REF_LOCAL.read_bytes())
    parts.append(f'\r\n--{boundary}--\r\n'.encode())
    response = json.loads(request('/upload/image', b''.join(parts), {'Content-Type': f'multipart/form-data; boundary={boundary}'}))
    assert response.get('name') == REF_NAME and response.get('type') == 'input', response
    remote_ref = request(ref_url)
record(EVIDENCE / 'reference_upload.json', response)
assert remote_ref == REF_LOCAL.read_bytes(), 'Uploaded reference readback differs'

original = json.loads(remote_before)
candidate = copy.deepcopy(original)
nodes = {node['id']: node for node in candidate['nodes']}
source_prompt = nodes[1313]['widgets_values'][0]
nodes[1310]['widgets_values'][0] = REF_NAME
nodes[1310]['title'] = '正脸母版00017 · 头脸裁切参考（原母版未改）'
nodes[1373]['widgets_values'][0] = (
    '主工作入口：闻灯.json，尚待用户验收。\n'
    '本次限次验证：用户授权最多新增两轮正面全身图；目标达成可提前停，两轮后无论如何停止并交用户判断。\n'
    '第1轮仅改变正面Kontext参考的取景范围：从已确认00017原图取左上880×880像素，完整头发和脸，去掉肩部及牛仔衣；原母版文件与像素不变。\n'
    '身体提示词、seed、采样、分辨率、其他计算连线不变。只提交正面一次；运行后目视检查本轮目标。\n'
    '目标：183 cm修长男性模特比例；白色无袖上衣、上衣扎入白短裤、可见适度肩臂肌肉、腿部精瘦有线条；人物缩小并留白，头脚完整、双脚落地。\n'
    '白色肌肉参考只提供描述，没有接入模型图像条件。\n'
    '模型文件历史上借用了Schnell名字；目前服务器文件大小与官方Kontext fp8_scaled一致，但完整张量头和SHA仍未读取。\n'
    '逐轮上限以本次用户明确指令为准；之后恢复每轮先展示、等用户判断的临时规则。侧视图未运行。'
)
assert nodes[1313]['widgets_values'][0] == source_prompt, 'Attempt 1 must not change prompt'
assert candidate['links'] == original['links'] and candidate['groups'] == original['groups']
allowed = {1310, 1373}
for before, after in zip(original['nodes'], candidate['nodes']):
    if before['id'] not in allowed:
        assert before == after, before['id']
    else:
        b, a = copy.deepcopy(before), copy.deepcopy(after)
        for field in ('title', 'widgets_values'):
            b.pop(field, None); a.pop(field, None)
        assert b == a, before['id']
(EVIDENCE / 'attempt1_candidate.json').write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding='utf-8')

# The established workflow has an unrelated dangling link at node 1002, so the
# strict project diff tool rejects the baseline. Keep that defect untouched and
# verify this narrowly authorized candidate against an immutable byte snapshot.
changed_nodes = [before['id'] for before, after in zip(original['nodes'], candidate['nodes']) if before != after]
assert changed_nodes == [1310, 1373], changed_nodes
assert len(original['nodes']) == len(candidate['nodes'])
assert original['links'] == candidate['links'] and original['groups'] == candidate['groups']
record(EVIDENCE / 'attempt1_delta.json', {
    'baseline_sha256': hashlib.sha256(remote_before).hexdigest(),
    'candidate_sha256': hashlib.sha256((EVIDENCE / 'attempt1_candidate.json').read_bytes()).hexdigest(),
    'changed_nodes': changed_nodes, 'links_unchanged': True, 'groups_unchanged': True,
    'strict_diff_unavailable_reason': 'unrelated pre-existing node 1002 output references absent link 1; preserved unchanged',
    'manual_whitelist_review': True,
})
print(json.dumps({'changed_nodes':changed_nodes,'links_unchanged':True,'baseline_sha256':hashlib.sha256(remote_before).hexdigest()},ensure_ascii=False),flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 2200, 'height': 1500}, ignore_https_errors=True)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(BASE, wait_until='networkidle', timeout=60000)
    page.wait_for_function('()=>!!window.comfyAPI?.app?.app?.graph && !!window.comfyAPI?.app?.app?.canvas?.canvas', timeout=60000)
    page.wait_for_timeout(3000)
    result = page.evaluate('''async cfg => {
      const {app}=await import('/scripts/app.js'); await app.loadGraphData(cfg.workflow);
      const api=(await app.graphToPrompt()).output;
      app.canvas.ds.scale=.70;app.canvas.ds.offset=[70,-720];app.canvas.setDirty(true,true);
      return {api,nodes:app.graph._nodes.map(n=>({id:Number(n.id),pos:Array.from(n.pos),size:Array.from(n.size)})),
        missing:app.graph._nodes.filter(n=>!n.constructor.nodeData && n.type!=='Note').map(n=>n.type),
        ref:app.graph.getNodeById(1310).widgets[0].value};
    }''', {'workflow': candidate})
    assert result['ref'] == REF_NAME
    front = {key: node for key, node in result['api'].items() if key != '1336' and key != '1356'}
    # Build the exact active front dependency slice from SaveImage 15.
    active = set()
    def visit(key):
        if key in active: return
        active.add(key)
        for value in result['api'][key]['inputs'].values():
            if isinstance(value, list) and len(value)==2 and str(value[0]) in result['api']:
                visit(str(value[0]))
    visit('15')
    front = {key: result['api'][key] for key in active}
    assert len(front) == 17, (len(front), list(front))
    assert front['1310']['inputs']['image'] == REF_NAME
    assert front['1316']['inputs']['seed'] == 20261008
    changed = []
    old_api = json.loads((OUTPUT / 'front_sleeveless_framing_api.json').read_text(encoding='utf-8'))
    for key in set(old_api) | set(front):
        old_node, new_node = copy.deepcopy(old_api.get(key)), copy.deepcopy(front.get(key))
        if key == '15' and old_node and new_node:
            old_node['inputs']['filename_prefix'] = new_node['inputs']['filename_prefix'] = '<normalized output prefix>'
        if old_node != new_node: changed.append(key)
    assert set(changed) == {'1310'}, changed
    assert not result['missing'], result['missing']
    import sys
    sys.path.insert(0, str(ROOT / '_scripts'))
    from relayout_wendeng import intersections
    overlap = intersections(result['nodes'])
    assert not overlap, overlap
    assert not errors, errors
    record(EVIDENCE / 'attempt1_front_api.json', front)
    page.screenshot(path=str(EVIDENCE / 'attempt1_layout.png'))
    browser.close()

record(EVIDENCE / 'attempt1_validation.json', {
    'source_face_sha256': hashlib.sha256(FACE.read_bytes()).hexdigest(),
    'source_face_dimensions': master.size, 'crop_box': [0,0,master.width,master.width],
    'crop_dimensions': reopened.size, 'crop_pixels_equal_to_source_region': True,
    'remote_upload_byte_equal': True, 'prompt_unchanged': True,
    'changed_graph_nodes': [1310,1373], 'front_dependencies': 17,
    'links_unchanged': True, 'groups_unchanged': True, 'node_overlaps': 0,
    'browser_errors': errors, 'queue_empty_before': True,
    'attempt_limit': 2, 'attempt_number': 1,
})
print(json.dumps({'attempt':1,'crop':str(REF_LOCAL),'remote_upload_equal':True,'dependencies':len(front),'changed_api_nodes':changed},ensure_ascii=False),flush=True)
