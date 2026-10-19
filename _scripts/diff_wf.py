# -*- coding: utf-8 -*-
"""增量比较 ComfyUI UI 工作流；完整 JSON 只在本地读取，报告只输出变更。"""
from __future__ import annotations
import argparse, copy, hashlib, json, sys, os, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATE_VERSION = 2
FORMAT = 0.4
READS = []

def read_bytes(path):
    raw = Path(path).read_bytes()
    READS.append((str(Path(path).resolve()), len(raw)))
    return raw

def sha256(path: Path) -> str:
    return hashlib.sha256(read_bytes(path)).hexdigest()

def validate_workflow(wf: Any, path: Path | None = None) -> None:
    label = str(path or 'workflow')
    if not isinstance(wf, dict) or not isinstance(wf.get('nodes'), list) or not isinstance(wf.get('links'), list):
        raise ValueError(f'{label} 不是 ComfyUI UI 工作流（需要 nodes/links 数组）')
    if 'version' in wf and wf['version'] != FORMAT:
        raise ValueError(f'{label} 工作流格式版本异常：{wf["version"]!r}，需要先人工检查')
    if any(not isinstance(n, dict) or type(n.get('id')) is not int or not isinstance(n.get('type'), str) for n in wf['nodes']):
        raise ValueError(f'{label} 含无效节点 ID 或类型')
    nodes = {n.get('id'): n for n in wf['nodes']}
    if len(nodes) != len(wf['nodes']) or None in nodes: raise ValueError(f'{label} 含重复或无效节点 ID')
    lids = set()
    for link in wf['links']:
        if not isinstance(link, list) or len(link) != 6: raise ValueError(f'{label} 含无效连线记录')
        lid, source, source_slot, target, target_slot = link[:5]
        if any(type(x) is not int for x in link[:5]): raise ValueError(f'{label} 连线 ID/端口必须为整数')
        if lid in lids: raise ValueError(f'{label} 含重复连线 ID：{lid!r}')
        if source not in nodes or target not in nodes or source_slot < 0 or target_slot < 0:
            raise ValueError(f'{label} 含悬空节点或负端口连线：{link!r}')
        outs, ins = nodes[source].get('outputs') or [], nodes[target].get('inputs') or []
        if source_slot >= len(outs) or target_slot >= len(ins): raise ValueError(f'{label} 连线 {lid} 端口越界')
        if ins[target_slot].get('link') != lid or lid not in (outs[source_slot].get('links') or []):
            raise ValueError(f'{label} 连线 {lid} 与端口反向引用不一致')
        lids.add(lid)
    links = _link_map(wf)
    for node in wf['nodes']:
        for i, slot in enumerate(node.get('inputs') or []):
            lid = slot.get('link')
            if lid is not None and (lid not in links or links[lid][3:5] != [node['id'], i]):
                raise ValueError(f'{label} 节点输入引用不存在的连线：{node.get("id")} / {slot.get("name")}')
        for i, slot in enumerate(node.get('outputs') or []):
            values = slot.get('links') or []
            if len(values) != len(set(values)): raise ValueError(f'{label} 输出连线重复')
            for lid in values:
                if lid not in links or links[lid][1:3] != [node['id'], i]:
                    raise ValueError(f'{label} 节点 {node["id"]} 输出端口 {i} 引用连线 {lid}，与连线表不一致')

def read_workflow(path: Path) -> dict[str, Any]:
    try:
        wf = json.loads(read_bytes(path))
    except (OSError, json.JSONDecodeError) as e: raise ValueError(f'无法读取有效 JSON：{path}: {e}') from e
    validate_workflow(wf, path); return wf

def _node_map(wf): return {n['id']: n for n in wf['nodes']}
def _link_map(wf): return {x[0]: x for x in wf['links']}

def _short(value, limit=180):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(',', ':'))
    text = text.replace('\n', '\\n')
    return text if len(text) <= limit else f'{text[:limit//2]} …({len(text)}字，完整值见本地报告) … {text[-limit//2:]}'

def _diff(a, b, path, out):
    if type(a) is not type(b): out.append({'path': path, 'old': copy.deepcopy(a), 'new': copy.deepcopy(b)})
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a: out.append({'path':f'{path}/{k}','op':'add','old':None,'new':copy.deepcopy(b[k])})
            elif k not in b: out.append({'path':f'{path}/{k}','op':'remove','old':copy.deepcopy(a[k]),'new':None})
            else: _diff(a[k], b[k], f'{path}/{k}', out)
    elif isinstance(a, list):
        for i in range(max(len(a), len(b))):
            if i >= len(a): out.append({'path':f'{path}/{i}','op':'add','old':None,'new':copy.deepcopy(b[i])})
            elif i >= len(b): out.append({'path':f'{path}/{i}','op':'remove','old':copy.deepcopy(a[i]),'new':None})
            else: _diff(a[i], b[i], f'{path}/{i}', out)
    elif a != b: out.append({'path': path, 'old': copy.deepcopy(a), 'new': copy.deepcopy(b)})

def _neighbors(wf, changed):
    up, down = set(), set()
    for lid, source, source_slot, target, target_slot, *_ in wf['links']:
        if target in changed: up.add(source)
        if source in changed: down.add(target)
    return {'upstream': sorted(up), 'downstream': sorted(down)}

def compare_workflows(old, new):
    validate_workflow(old); validate_workflow(new)
    A, B, changes, reasons = _node_map(old), _node_map(new), [], set()
    for k in sorted(set(A) | set(B)):
        if k not in A: changes.append({'path': f'/nodes/{k}', 'old': None, 'new': copy.deepcopy(B[k])}); reasons.add('structure')
        elif k not in B: changes.append({'path': f'/nodes/{k}', 'old': copy.deepcopy(A[k]), 'new': None}); reasons.add('structure')
        else:
            local=[]; _diff(A[k], B[k], f'/nodes/{k}', local); changes.extend(local)
            if any(A[k].get(f) != B[k].get(f) for f in ('type','inputs','outputs','mode')): reasons.add('structure')
            if local and any(word in B[k]['type'].lower() for word in ('loader','loadimage','reference')): reasons.add('dependency')
    LA, LB = _link_map(old), _link_map(new)
    for k in sorted(set(LA) | set(LB)): _diff(LA.get(k), LB.get(k), f'/links/{k}', changes)
    if LA != LB: reasons.add('structure')
    MA={k:v for k,v in old.items() if k not in {'nodes','links'}}; MB={k:v for k,v in new.items() if k not in {'nodes','links'}}
    _diff(MA, MB, '/metadata', changes)
    if MA != MB: reasons.add('format-or-metadata')
    ids={int(c['path'].split('/')[2]) for c in changes if c['path'].startswith('/nodes/') and c['path'].split('/')[2].isdigit()}
    for k in set(LA) | set(LB):
        if LA.get(k) != LB.get(k):
            for link in (LA.get(k), LB.get(k)):
                if link: ids.update((link[1], link[3]))
    if len(ids) > max(10, len(A)//4): reasons.add('large-change')
    if changes and not reasons: reasons.add('parameters')
    scope='unchanged' if not changes else ('local' if reasons == {'parameters'} else 'expanded-review')
    old_ctx, new_ctx = _neighbors(old, ids), _neighbors(new, ids)
    context = {}
    for name, nodes, ctx in [('old', A, old_ctx), ('new', B, new_ctx)]:
        context[name] = {str(i): {'type':nodes[i]['type'], **_neighbors(old if name == 'old' else new, {i})}
                         for i in sorted(ids | set(ctx['upstream']) | set(ctx['downstream'])) if i in nodes}
    return {'changes': changes, 'scope': scope, 'review_reasons': sorted(reasons), 'context': context,
            'old_counts': {'nodes': len(old['nodes']), 'links': len(old['links'])}, 'new_counts': {'nodes': len(new['nodes']), 'links': len(new['links'])}}

def compare_files(old_path, new_path):
    old_path, new_path = Path(old_path), Path(new_path)
    a, b = read_bytes(old_path), read_bytes(new_path)
    r=compare_workflows(json.loads(a),json.loads(b))
    r.update({'old_path':str(old_path.resolve()),'new_path':str(new_path.resolve()),'old_sha256':hashlib.sha256(a).hexdigest(),'new_sha256':hashlib.sha256(b).hexdigest(),'parse_skipped':False})
    return r

def snapshot(raw, directory):
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    dest = directory / (hashlib.sha256(raw).hexdigest() + '.baseline.json')
    if dest.exists():
        if read_bytes(dest) != raw: raise ValueError('归档同名文件内容冲突')
    else:
        with dest.open('xb') as f: f.write(raw)
    return dest.resolve()

def write_json(path, value, exclusive=False):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open('x', encoding='utf-8') as f: json.dump(value, f, ensure_ascii=False, indent=2)
    else:
        temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
        temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        os.replace(temp, path)

def init_state(baseline_path, state_path):
    baseline_path,state_path=Path(baseline_path),Path(state_path)
    if state_path.exists(): raise ValueError('状态已存在；请使用增量推进，不覆盖已有状态')
    raw=read_bytes(baseline_path); wf=json.loads(raw); validate_workflow(wf)
    dest=snapshot(raw,state_path.parent/'baselines')
    s={'state_version':STATE_VERSION,'baseline_path':str(dest),'baseline_sha256':hashlib.sha256(raw).hexdigest(),'format':wf.get('version',FORMAT),'nodes':len(wf['nodes']),'links':len(wf['links']),'validated_at':datetime.now(timezone.utc).isoformat()}
    write_json(state_path,s,exclusive=True); return s

def _load_state(state_path):
    try: s=json.loads(read_bytes(state_path))
    except (OSError,json.JSONDecodeError) as e: raise ValueError(f'无法读取状态文件：{state_path}: {e}') from e
    if s.get('state_version') != STATE_VERSION or not s.get('baseline_path') or not s.get('baseline_sha256'): raise ValueError('状态文件无效，需要重新建立基准')
    p=Path(s['baseline_path'])
    if not p.exists() or sha256(p) != s['baseline_sha256']: raise ValueError('基准文件已变化或不存在，需要人工确认')
    return s

def compare_state(state_path, current_path):
    s=_load_state(Path(state_path)); current_hash=sha256(Path(current_path))
    if current_hash == s['baseline_sha256']:
        return {'changes':[],'scope':'unchanged','review_reasons':[],'parse_skipped':True,'old_sha256':s['baseline_sha256'],'new_sha256':current_hash,'old_counts':{'nodes':s.get('nodes'),'links':s.get('links')},'new_counts':{'nodes':s.get('nodes'),'links':s.get('links')}}
    r=compare_files(Path(s['baseline_path']),Path(current_path)); r['state_path']=str(state_path); return r

def advance_state(state_path,current_path,report,reviewed_sha,archive_dir,expanded_reviewed=False):
    state_path,current_path,archive_dir=Path(state_path),Path(current_path),Path(archive_dir); s=_load_state(state_path)
    if reviewed_sha != report.get('new_sha256') or reviewed_sha != sha256(current_path): raise ValueError('审核哈希与当前工作流不一致，拒绝推进基准')
    if report.get('old_sha256') != s['baseline_sha256']: raise ValueError('差异报告不是基于当前基准生成，拒绝推进基准')
    actual = compare_files(s['baseline_path'],current_path)
    if actual['new_sha256'] != reviewed_sha or actual['changes'] != report['changes']: raise ValueError('文件或差异报告已变化')
    if actual['scope'] == 'expanded-review' and not expanded_reviewed: raise ValueError('须完成扩大复核后使用 --expanded-reviewed')
    raw = read_bytes(current_path)
    if hashlib.sha256(raw).hexdigest() != reviewed_sha: raise ValueError('工作流在推进前发生变化')
    wf=json.loads(raw); validate_workflow(wf)
    archive_dir.mkdir(parents=True,exist_ok=True); stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    dest=snapshot(raw,archive_dir); snapshot(read_bytes(s['baseline_path']),archive_dir)
    d=dict(actual); d.update({'reviewed_sha256':reviewed_sha,'expanded_reviewed':expanded_reviewed,'advanced_at':stamp})
    write_json(archive_dir/f'{stamp}.delta.json',d,exclusive=True)
    if _load_state(state_path) != s: raise ValueError('状态在推进前发生变化')
    s.update({'baseline_path':str(dest),'baseline_sha256':reviewed_sha,'nodes':len(wf['nodes']),'links':len(wf['links']),'validated_at':datetime.now(timezone.utc).isoformat()})
    write_json(state_path,s)

def render_report(r, max_chars=5000):
    lines=[f"范围：{r.get('scope')}；旧规模 {r.get('old_counts')} → 新规模 {r.get('new_counts')}",f"变更：{len(r.get('changes',[]))}；复核原因：{', '.join(r.get('review_reasons') or ['无'])}"]
    if r.get('parse_skipped'): lines.append('哈希一致：已跳过 JSON 解析。'); return '\n'.join(lines)
    for c in r.get('changes',[])[:30]: lines.append(f"{_short(c['path'])}: {_short(c.get('old'))} → {_short(c.get('new'))}")
    lines.append('一跳节点：' + _short({k:list(v) for k,v in r.get('context',{}).items()}))
    output='\n'.join(lines)
    if len(output)>max_chars or len(r.get('changes',[]))>30:
        output=output[:max(0,max_chars-50)]+'\n[摘要已限长；完整字段与上下游见本地报告]'
    return output[:max_chars]

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('old',nargs='?'); p.add_argument('new',nargs='?')
    p.add_argument('--init-state'); p.add_argument('--state')
    p.add_argument('--advance',action='store_true'); p.add_argument('--reviewed-sha')
    p.add_argument('--expanded-reviewed',action='store_true')
    p.add_argument('--archive-dir',default='docs/archive/workflow-snapshots/token-deltas')
    p.add_argument('--report',help='完整差异报告，不覆盖现有文件')
    p.add_argument('--usage-log',default='docs/generated/token-usage.jsonl')
    p.add_argument('--max-chars',type=int,default=5000)
    p.add_argument('--input-tokens',type=int); p.add_argument('--cached-input-tokens',type=int)
    p.add_argument('--usage-source',help='实际用量的来源/请求 ID；不能填估算值')
    a=p.parse_args(argv)
    READS.clear()
    metrics_safe=False
    try:
        if not 600 <= a.max_chars <= 10000: raise ValueError('--max-chars 应为 600–10000')
        if a.input_tokens is not None and (a.input_tokens < 0 or not a.usage_source): raise ValueError('实际 Token 需要非负数和 --usage-source')
        if a.cached_input_tokens is not None and (a.input_tokens is None or not 0 <= a.cached_input_tokens <= a.input_tokens): raise ValueError('缓存 Token 必须在实际输入 Token 范围内')
        if a.advance and (not a.state or not a.reviewed_sha or a.init_state): raise ValueError('--advance 需要 --state 和 --reviewed-sha，不能与初始化合用')
        protected={Path(x).resolve() for x in (a.old,a.new,a.init_state,a.state) if x}
        if a.state and not a.init_state: protected.add(Path(_load_state(a.state)['baseline_path']).resolve())
        output_paths=[Path(x).resolve() for x in (a.report,a.usage_log) if x]
        if len(set(output_paths)) != len(output_paths) or any(x in protected for x in output_paths): raise ValueError('报告/日志不能覆盖输入、状态或基准')
        if a.report and Path(a.report).exists(): raise ValueError('报告文件已存在，使用新路径')
        metrics_safe=True
        if a.init_state:
            if not a.state: p.error('--init-state 需要 --state')
            s=init_state(a.init_state,a.state)
            r={'scope':'initialized','changes':[],'review_reasons':[], 'new_counts':{'nodes':s['nodes'],'links':s['links']},'parse_skipped':False}
        elif a.state:
            current = a.new or a.old
            if not current: p.error('--state 需要提供当前工作流路径')
            r=compare_state(a.state,current)
        elif a.old and a.new: r=compare_files(a.old,a.new)
        else: p.print_help(); return 2
        report_path=None
        if a.report or r['changes']:
            report_path=Path(a.report) if a.report else Path('docs/generated/workflow-diffs')/(uuid.uuid4().hex+'.json')
            write_json(report_path,r,exclusive=True)
        if a.advance:
            advance_state(a.state,current,r,a.reviewed_sha,a.archive_dir,a.expanded_reviewed)
        footer=f'\n报告：{report_path}' if report_path else ''
        footer+=f'\n用量：{a.usage_log}'
        if a.advance: footer+='\n已归档并推进比较基准（非用户验收）。'
        output=(render_report(r,max(100,a.max_chars-len(footer)-1))+footer)[:a.max_chars-1]+'\n'
        metrics={'timestamp':datetime.now(timezone.utc).isoformat(),'scope':'diff_wf invocation only',
                 'files_read':len({x[0] for x in READS}),'read_operations':len(READS),
                 'local_read_bytes':sum(x[1] for x in READS),'console_chars':len(output),'console_utf8_bytes':len(output.encode('utf-8')),
                 'change_count':len(r['changes']),'parse_skipped':r['parse_skipped'],
                 'input_tokens':a.input_tokens,'cached_input_tokens':a.cached_input_tokens,'usage_source':a.usage_source}
        log=Path(a.usage_log); log.parent.mkdir(parents=True,exist_ok=True)
        with log.open('a',encoding='utf-8') as f: f.write(json.dumps(metrics,ensure_ascii=False)+'\n')
        print(output,end='')
        return 0
    except (ValueError,OSError,TypeError,KeyError) as e:
        output=f'错误：{str(e)[:1500]}\n'
        if metrics_safe:
            metrics={'timestamp':datetime.now(timezone.utc).isoformat(),'scope':'diff_wf invocation only',
                     'status':'error','files_read':len({x[0] for x in READS}),'read_operations':len(READS),
                     'local_read_bytes':sum(x[1] for x in READS),'console_chars':len(output),
                     'console_utf8_bytes':len(output.encode('utf-8')),'input_tokens':a.input_tokens,
                     'cached_input_tokens':a.cached_input_tokens,'usage_source':a.usage_source}
            try:
                log=Path(a.usage_log); log.parent.mkdir(parents=True,exist_ok=True)
                with log.open('a',encoding='utf-8') as f: f.write(json.dumps(metrics,ensure_ascii=False)+'\n')
            except OSError: pass  # Report the original failure even if metrics cannot be written.
        print(output,end='',file=sys.stderr); return 1

if __name__ == '__main__': raise SystemExit(main())
