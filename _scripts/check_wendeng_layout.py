"""Load a candidate in a fresh browser; route cross-group wires for review."""
import json
import os
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright
from relayout_wendeng import intersections
from wf_api import build_api

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs/archive/workflow-snapshots/闻灯恢复-2026-10-10'
STAGE = sys.argv[1] if len(sys.argv)>1 else 'layout'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 2200, 'height': 1500}, ignore_https_errors=True)
    page.goto(os.environ['COMFY_BASE'], wait_until='networkidle', timeout=60000)
    page.wait_for_function("async()=>{try{return !!(await import('/scripts/app.js')).app?.graph}catch(e){return false}}", timeout=30000)
    candidate = json.loads((OUT / (STAGE+'_candidate.json')).read_text(encoding='utf-8'))
    result = page.evaluate("""async wf => {
        const {app} = await import('/scripts/app.js');
        await app.loadGraphData(wf);
        const graph = app.graph;
        const groups=wf.groups.slice(1);
        const nodes=new Map(graph._nodes.map(n=>[Number(n.id),n]));
        function groupFor(n){return groups.find(g=>{const [x,y,w,h]=g.bounding;return n.pos[0]>=x&&n.pos[0]<x+w&&n.pos[1]>=y&&n.pos[1]<y+h})}
        const buses = new Map();
        let routed=0;
        for(const row of wf.links){
            const [id,src,slot,dst,dslot]=row;
            const s=nodes.get(src),d=nodes.get(dst),sg=groupFor(s),dg=groupFor(d);
            if(sg.id===dg.id) continue;
            const link=graph.links.get(id);if(!link)throw new Error('missing link '+id);
            const start=Array.from(s.getConnectionPos(false,slot));
            const end=Array.from(d.getConnectionPos(true,dslot));
            const key=src+':'+slot+':'+(d.pos[0]<4000?'left':'right');
            if(!buses.has(key)) buses.set(key,buses.size);
            const idx=buses.get(key);
            const bus=d.pos[0]<4000?-160-idx*12:3950+(idx%20)*12;
            const sy=sg.id===3?sg.bounding[1]+40:sg.bounding[1]+sg.bounding[3]+20;
            const dy=dg.bounding[1]+42;
            const points=[[start[0]+25,start[1]],[start[0]+25,sy],[bus,sy],[bus,dy],[end[0]-24,dy],[end[0]-24,end[1]]];
            for(const point of points) graph.createReroute(point,link);
            routed++;
        }
        const serialized=graph.serialize();
        return {extra:serialized.extra, routed, nodes:graph._nodes.map(n=>({id:Number(n.id),pos:Array.from(n.pos),size:Array.from(n.size)})), input1360:graph.getNodeById(1360).inputs.map(s=>({name:s.name,type:s.type,link:s.link}))};
    }""", candidate)
    assert len(result['nodes']) == len(candidate['nodes'])
    assert not intersections(result['nodes'])
    candidate['extra']['reroutes'] = result['extra']['reroutes']
    candidate['extra']['linkExtensions'] = result['extra']['linkExtensions']
    candidate['extra']['ds'] = {'scale': 0.65, 'offset': [60, -730]}
    parent = candidate['groups'][0]
    right = parent['bounding'][0] + parent['bounding'][2]
    parent['bounding'][0] = min(r['pos'][0] for r in candidate['extra']['reroutes']) - 70
    parent['bounding'][2] = right - parent['bounding'][0]
    source = json.loads((OUT / ('remote_before.json' if STAGE=='layout' else STAGE+'_candidate.json')).read_text(encoding='utf-8'))
    assert build_api(candidate)[0] == build_api(source)[0]
    (OUT / (STAGE+'_routed.json')).write_text(json.dumps(candidate, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / (STAGE+'_browser_validation.json')).write_text(json.dumps({'nodes':len(candidate['nodes']),'links':len(candidate['links']),'node_overlaps':0,'routed_links':result['routed'],'routing_execution_unchanged':True,'input1360':result['input1360']},ensure_ascii=False,indent=2),encoding='utf-8')
    if STAGE=='body':
        prompt=page.evaluate("async()=>{const {app}=await import('/scripts/app.js');return (await app.graphToPrompt()).output}")
        (OUT/'body_browser_api.json').write_text(json.dumps(prompt,ensure_ascii=False,indent=2),encoding='utf-8')
    # Dismiss a server-side informational toast in this review browser only.
    buttons = page.locator('.p-toast-close-button')
    for i in range(buttons.count()):
        try:
            buttons.nth(i).click(timeout=1000)
        except Exception:
            pass
    for name, scale, offset in [('layout_routed_overview',0.18,[620,320]),('layout_routed_front',0.70,[70,-720]),('layout_routed_three_views',0.38,[140,-760])]:
        page.evaluate("""async cfg=>{const {app}=await import('/scripts/app.js');app.canvas.ds.scale=cfg.scale;app.canvas.ds.offset=cfg.offset;app.canvas.setDirty(true,true)}""",{'scale':scale,'offset':offset})
        page.wait_for_timeout(1200)
        page.screenshot(path=str(OUT/(name.replace('layout',STAGE)+'.png')))
    browser.close()
    print(json.dumps({'nodes':len(candidate['nodes']),'routed_links':result['routed'],'overlaps':0,'routing_execution_unchanged':True}))
