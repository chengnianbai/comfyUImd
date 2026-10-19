"""逐个检查候选 SD1.5 LoRA 仓库里的文件，看是否真能用于 SD1.5。"""
import json
import urllib.request

urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

CANDIDATES = [
    "markredito/FilmGrain-LoRA-stablediffusion",
    "Dcry/add-more-details-detail-enhancer-tweaker-lora",
    "amaru96vn/Add_Detail_Lora-1.5",
    "Boxer11/adddetailLora",
    "luvGPT/add-detail-lora",
    "izitn/FilmGrainLoRA",
    "getdiffus/SDaB1-Detail-Tweaker-LoRA-LoRA",
    "niitokikei/DetailTweaker",
]


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


for mid in CANDIDATES:
    print("\n=== %s ===" % mid)
    try:
        info = get("https://hf-mirror.com/api/models/" + mid)
    except Exception as e:
        print("   读取失败:", type(e).__name__, e)
        continue
    print("   tags:", ",".join(info.get("tags", [])))
    print("   downloads:", info.get("downloads"), " likes:", info.get("likes"))
    try:
        tree = get("https://hf-mirror.com/api/models/%s/tree/main" % mid)
    except Exception as e:
        print("   文件列表失败:", type(e).__name__, e)
        continue
    for f in tree:
        sz = f.get("size", 0)
        if f.get("type") == "file" and sz > 1024:
            print("   %-52s %8.1f MB" % (f["path"], sz / 1048576))
