"""Build a reviewable candidate from the saved graph; does not save remotely."""
import copy
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright
from relayout_wendeng import intersections

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / 'docs/archive/workflow-snapshots/闻灯恢复-2026-10-12'
EXPERIMENT = ROOT / '系列-夜市百相簿/02-角色/闻灯/设定图/全身验证-2026-10-12'
wf = json.loads((EVIDENCE / 'remote_before.json').read_text(encoding='utf-8'))
source = copy.deepcopy(wf)
# Old route coordinates refer to the former positions. Rebuild routing after moving.
wf['extra'].pop('reroutes', None)
wf['extra'].pop('linkExtensions', None)
for node in wf['nodes']:
    if 905 <= node['pos'][1] < 1840 and node['pos'][0] < 4000 and node['id'] not in (14, 15):
        node['pos'][1] += 6800
for group in wf['groups']:
    if group['id'] == 4:
        group['bounding'][1] += 6800
        group['title'] = '历史 · 原正面生成链 / B 参数保留'
    if group['id'] == 2:
        group['bounding'][3] = 8700
wf['groups'].append({'id': 15, 'title': '02 · 正面比例候选 / 保留已认可的脸',
    'bounding': [45, 905, 3770, 1020], 'color': '#387d76', 'font_size': 28, 'flags': {}})
api = json.loads((EXPERIMENT / 'P_front_proportion_api.json').read_text(encoding='utf-8'))
api.pop('9000')
api['9200']['inputs']['image'] = 'wendeng_integrated_front.png'
positions = {'9200':[80,1000], '9201':[600,1000], '9202':[600,1210],
    '9203':[600,1420], '9204':[600,1630], '9205':[1040,1210],
    '9206':[1040,1480], '9207':[1520,1000], '9208':[1930,1210], '9209':[2340,1420]}
titles = {'9200':'已认可正面成图 / 脸部不重生成', '9201':'保留头脸 / 顶部 800px',
    '9202':'上身原段 / 1216px', '9203':'下半身原段 / 1248px', '9204':'保留脚部 / 底部 320px',
    '9205':'比例调节① 上身高度 1032', '9206':'比例调节② 下半身高度 1432',
    '9207':'拼接头部与上身', '9208':'接入下半身', '9209':'接入原脚部 / 2048×3584'}
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width':2200, 'height':1500}, ignore_https_errors=True)
    page.goto(os.environ['COMFY_BASE'], wait_until='networkidle', timeout=60000)
    page.wait_for_function('()=>!!window.comfyAPI?.app?.app?.graph', timeout=45000)
    result = page.evaluate('''async cfg => {
        const {app} = await import('/scripts/app.js');
        await app.loadGraphData(cfg.wf);
        const graph=app.graph, remap={};
        for(const [key,item] of Object.entries(cfg.api)){
            const node=LiteGraph.createNode(item.class_type);
            if(!node)throw Error('Missing node type '+item.class_type);
            node.id=Number(key)-7820; remap[key]=node;
            graph.add(node);node.pos=cfg.positions[key];node.title=cfg.titles[key];
            node.size=[key==='9200'?440:350, key==='9200'?620:Math.max(node.size[1],150)];
            for(const [name,value] of Object.entries(item.inputs)){
                if(Array.isArray(value))continue;
                const widget=node.widgets?.find(w=>w.name===name);
                if(!widget)throw Error('No widget '+key+'.'+name);
                widget.value=value;
            }
        }
        for(const [key,item] of Object.entries(cfg.api))for(const [name,value] of Object.entries(item.inputs)){
            if(!Array.isArray(value))continue;
            const node=remap[key], slot=node.inputs.findIndex(s=>s.name===name);
            if(slot<0)throw Error('No input '+key+'.'+name);
            remap[value[0]].connect(value[1],node,slot);
        }
        for(const id of [14,15])remap['9209'].connect(0,graph.getNodeById(id),0);
        graph.getNodeById(15).title='正面比例候选 / 待验收';
        graph.getNodeById(15).widgets.find(w=>w.name==='filename_prefix').value='闻灯/正面比例-待验收';
        graph.getNodeById(14).title='预览 / 原脸保留的正面比例候选';
        graph.getNodeById(316).mode=2;
        graph.getNodeById(316).title='暂停输出 · 原斜侧面 / 待替换';
        graph.getNodeById(346).mode=2;
        graph.getNodeById(346).title='暂停输出 · 背面 / 待比例确认后同步';
        const note=graph.getNodeById(1373);
        note.widgets[0].value='当前主文件待验收，不是最终档。\\n\\n默认运行：从已认可的 integrated_front 成图调整身体比例。顶部800像素保留原脸，底部320像素保留脚部，不重新采样正面。\\n\\n比例参数：节点1385上身高度1032；节点1386下半身高度1432，两项之和保持2464。肩宽不变。\\n\\n侧面仍在验证；旧斜侧面及背面输出暂时停用。原正面B生成参数保留在下方历史分组。\\n\\n换实例时上传同目录“参考素材”中的输入图，并核对模型。';
        const pre=await app.graphToPrompt();
        const serialized=graph.serialize();
        return {workflow:serialized,api:pre.output,nodes:graph._nodes.map(n=>({id:Number(n.id),pos:Array.from(n.pos),size:Array.from(n.size)}))};
    }''', {'wf':wf, 'api':api, 'positions':positions, 'titles':titles})
    assert not intersections(result['nodes']), intersections(result['nodes'])
    graph = result['workflow']
    # Routing is presentation only. Compare browser APIs before and after routing.
    routed = page.evaluate('''async()=>{
        const {app}=await import('/scripts/app.js');const g=app.graph;
        const groups=g.serialize().groups.filter(x=>x.id!==2);
        const groupFor=n=>groups.find(x=>{const [a,b,w,h]=x.bounding;return n.pos[0]>=a&&n.pos[0]<a+w&&n.pos[1]>=b&&n.pos[1]<b+h});
        const rows=Array.from(g.links.values());let count=0;
        for(const link of rows){
            const s=g.getNodeById(link.origin_id),d=g.getNodeById(link.target_id),sg=groupFor(s),dg=groupFor(d);
            if(!sg||!dg||sg.id===dg.id)continue;
            const a=Array.from(s.getConnectionPos(false,link.origin_slot)),b=Array.from(d.getConnectionPos(true,link.target_slot));
            const bus=d.pos[0]<4000?-160-(count%26)*12:3950+(count%20)*12;
            const sy=sg.id===3?sg.bounding[1]+40:sg.bounding[1]+sg.bounding[3]+20,dy=dg.bounding[1]+42;
            for(const xy of [[a[0]+25,a[1]],[a[0]+25,sy],[bus,sy],[bus,dy],[b[0]-24,dy],[b[0]-24,b[1]]])g.createReroute(xy,link);
            count++;
        }
        return {workflow:g.serialize(),api:(await app.graphToPrompt()).output,routed:count};
    }''')
    assert routed['api'] == result['api']
    for key, value in [('proportion_candidate',routed['workflow']),('proportion_browser_api',routed['api'])]:
        (EVIDENCE/(key+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    page.evaluate('''async()=>{const {app}=await import('/scripts/app.js');app.canvas.ds.scale=.65;app.canvas.ds.offset=[60,-810];app.canvas.setDirty(true,true)}''')
    page.wait_for_timeout(500)
    page.screenshot(path=str(EVIDENCE/'proportion_layout.png'))
    browser.close()
    print(json.dumps({'nodes':len(routed['workflow']['nodes']), 'links':len(routed['workflow']['links']), 'overlaps':0,'routed_links':routed['routed']},ensure_ascii=False))
