"""Bounded, branch-only validation jobs for the saved Wengdeng workflow."""
import argparse
import json
import os
from pathlib import Path
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get('COMFY_RUN_OUTPUT', str(ROOT / '系列-夜市百相簿/02-角色/闻灯/设定图/全身验证-2026-10-10')))
OLD = ROOT / '系列-夜市百相簿/02-角色/闻灯/设定图/锁脸诊断-2026-10-09'
OUTPUT_PREFIX = os.environ.get('COMFY_OUTPUT_PREFIX', 'codex_wendeng_20261010')
CONTEXT = ssl._create_unverified_context()


def request(path, data=None):
    base = os.environ['COMFY_BASE'].rstrip('/')
    req = urllib.request.Request(base + path, data=data,
                                 headers={'Content-Type': 'application/json'} if data else {})
    try:
        return urllib.request.urlopen(req, context=CONTEXT, timeout=40).read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode('utf-8', 'replace')) from exc


def run(name, api):
    OUT.mkdir(parents=True, exist_ok=True)
    outputs = [key for key, node in api.items() if node['class_type'] == 'SaveImage']
    assert len(outputs) == 1, outputs
    if outputs[0] != '9000':
        api['9000'] = api.pop(outputs[0])
    api['9000']['inputs']['filename_prefix'] = OUTPUT_PREFIX.rstrip('/') + '/' + name
    (OUT / (name + '_api.json')).write_text(json.dumps(api, ensure_ascii=False, indent=2), encoding='utf-8')
    response = json.loads(request('/prompt', json.dumps({'prompt': api, 'client_id': 'codex-wendeng-resume-20261010'}).encode('utf-8')))
    (OUT / (name + '_job.json')).write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Submitted', name, response, flush=True)
    if response.get('node_errors'):
        raise RuntimeError(response['node_errors'])
    prompt_id = response['prompt_id']
    deadline = time.monotonic() + 1500
    while time.monotonic() < deadline:
        history = json.loads(request('/history/' + prompt_id))
        if prompt_id in history:
            item = history[prompt_id]
            (OUT / (name + '_history.json')).write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding='utf-8')
            if item.get('status', {}).get('status_str') != 'success':
                raise RuntimeError(item.get('status'))
            files = item['outputs']['9000']['images']
            for i, info in enumerate(files):
                raw = request('/view?' + urllib.parse.urlencode(info))
                target = OUT / (name + ('_%02d' % i if len(files) > 1 else '') + '.png')
                target.write_bytes(raw)
                print('Downloaded', str(target), len(raw), flush=True)
            return
        time.sleep(5)
    raise TimeoutError('Job still unconfirmed; inspect saved prompt_id before resubmitting')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('name', choices=['G_side_from_body', 'H_front_seed2', 'I_side_two_refs', 'J_side_angle'])
    args = parser.parse_args()
    if args.name == 'H_front_seed2':
        api = json.loads((OLD / 'B_full_reference_api.json').read_text(encoding='utf-8'))
        api['1316']['inputs']['seed'] = 20261010
    else:
        api = json.loads((OLD / 'F_back_from_body_api.json').read_text(encoding='utf-8'))
        api['1353']['inputs']['text'] = (
            'Rotate this same man and his entire body exactly 90 degrees to face the left edge of the image. '
            'A strict left-facing side profile of the whole standing person, not a three-quarter view. '
            'His face, chest, pelvis, knees and both bare feet all face left. Only one eye is visible. '
            'Keep the same man, facial features, curly black hair, moustache, chin beard, skin tone, '
            'body build, plain white crew-neck T-shirt and plain white shorts. '
            'Keep the camera at the same distance and keep the same full-length head-to-toe framing as the input. '
            'The complete hair, legs, heels and toes must be inside the image with white margins above and below. '
            'Arms hanging naturally at his sides, standing straight. Plain white studio background, soft even lighting.'
        )
        if args.name == 'I_side_two_refs':
            api['9010'] = {'class_type': 'LoadImage', 'inputs': {'image': '闻灯-脸部左侧-成品_00009_.png [output]'}}
            api['9011'] = {'class_type': 'FluxKontextImageScale', 'inputs': {'image': ['9010', 0]}}
            api['9012'] = {'class_type': 'VAEEncode', 'inputs': {'pixels': ['9011', 0], 'vae': ['1026', 0]}}
            api['9013'] = {'class_type': 'ReferenceLatent', 'inputs': {'conditioning': ['1355', 0], 'latent': ['9012', 0]}}
            api['1356']['inputs']['positive'] = ['9013', 0]
        if args.name == 'J_side_angle':
            api['1350']['inputs']['image'] = 'codex_wendeng_20261010/I_side_two_refs_00001_.png [output]'
            api['1353']['inputs']['text'] = (
                'Keep this exact man, his head and face, hairstyle, white T-shirt and white shorts unchanged. '
                'Turn only his shoulders, chest, hips, legs and feet further to his left so his entire body '
                'is seen in an exact 90-degree side profile, matching the direction of his face. '
                'The far shoulder, far arm and far leg are fully hidden behind the near ones. '
                'Both feet point straight toward the left edge of the picture. '
                'Keep the complete standing figure from hair to bare toes inside the frame with white margins. '
                'Keep the same white background and lighting.'
            )
    run(args.name, api)
