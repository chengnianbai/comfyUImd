"""Reload the saved graph after frontend setup and inspect the rendered canvas."""
import json
import os
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '_scripts'))
from relayout_wendeng import intersections

workflow = json.loads((ROOT / '系列-夜市百相簿/02-角色/闻灯/工作流/闻灯.json').read_text(encoding='utf-8'))
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 2200, 'height': 1500}, ignore_https_errors=True)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(os.environ['COMFY_BASE'], wait_until='networkidle', timeout=60000)
    page.wait_for_function('()=>!!window.comfyAPI?.app?.app?.graph && !!window.comfyAPI?.app?.app?.canvas?.canvas', timeout=60000)
    page.wait_for_timeout(3000)
    print('Initial UI text:', page.locator('body').inner_text()[:800], flush=True)
    result = page.evaluate('''async wf=>{
        const {app}=await import('/scripts/app.js');
        await app.loadGraphData(wf);
        app.canvas.ds.scale=.70;app.canvas.ds.offset=[70,-720];app.canvas.setDirty(true,true);
        return {nodes:app.graph._nodes.map(n=>({id:Number(n.id),pos:Array.from(n.pos),size:Array.from(n.size)})),
          text:app.graph.getNodeById(1313).widgets[0].value,
          noteVirtual:app.graph.getNodeById(1373).isVirtualNode,
          api:(await app.graphToPrompt()).output};
    }''', workflow)
    assert result['text'] == next(n for n in workflow['nodes'] if n['id'] == 1313)['widgets_values'][0]
    overlaps = intersections(result['nodes'])
    assert not overlaps, overlaps
    page.wait_for_timeout(2000)
    page.screenshot(path=str(OUT / 'saved_front_layout.png'))
    report = {'node_count': len(result['nodes']), 'overlaps': overlaps, 'body_text_matches': True,
              'browser_errors': errors, 'note_virtual': result.get('noteVirtual')}
    (OUT / 'saved_browser_api.json').write_text(json.dumps(result['api'], ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'saved_browser_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    browser.close()
