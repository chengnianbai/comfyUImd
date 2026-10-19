# -*- coding: utf-8 -*-
"""把浅灰背景校正为纯白 —— 只动背景，绝不碰人物

为什么需要后处理：SDXL 对 `pure white background` 通常只给**浅灰**（约 205-245），
提示词层面压不成 255，只能生成后做像素级处理。

算法（v2，修掉 v1 的两个致命缺陷）：
  v1 缺陷 1：从**底边**取种子 -> 人物（衬衫）触到画面底边时，floodfill 顺着衣服倒灌，
             把浅蓝衬衫刷成白色。
  v1 缺陷 2：只按亮度差判断 -> 背景浅灰(240,240,240) 与衬衫高光(230,235,245) 亮度接近，
             被当成同一区域。

  v2 做法：
    1) **只从上边缘 / 左右边缘中"确属背景"的点生长**，永不从底边取种子；
    2) 背景判定 = 「中性（RGB 三通道极差 <= spread）**且** 与背景参考色的通道绝对差之和 <= tol」，
       蓝色衬衫天然带色偏（b 比 r 大 20+），因此不会被判成背景；
    3) 用「二值掩膜 + thresh=0 的 floodfill」取**连通域**，保证只填连通到上边缘的那片背景；
    4) 掩膜轻微膨胀后合成纯白，边缘自然。

用法：
  python post_whitebg.py <文件或目录> [--spread 14] [--tol 26]
"""
import sys, os, glob
from PIL import Image, ImageDraw, ImageFilter

SPREAD = 14      # 三通道极差上限：超过即认为"有色偏"（衣服/皮肤），不当背景
TOL = 26         # 与背景参考色的通道绝对差之和上限


def bg_ref(img, corner=24):
    """取四角小块的中位色作为背景参考（人物在中间，四角必是背景）"""
    w, h = img.size
    px = img.load()
    samples = []
    for cx, cy in [(0, 0), (w - corner, 0), (0, h - corner), (w - corner, h - corner)]:
        for x in range(cx, cx + corner, 3):
            for y in range(cy, cy + corner, 3):
                samples.append(px[x, y])
    samples.sort(key=lambda c: sum(c))
    med = samples[len(samples) // 2]
    return med


def is_bg(c, ref, spread, tol):
    if max(c) - min(c) > spread:
        return False
    return abs(c[0] - ref[0]) + abs(c[1] - ref[1]) + abs(c[2] - ref[2]) <= tol


def fix(path, out, spread=SPREAD, tol=TOL):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    ref = bg_ref(img)
    px = img.load()

    # 1) 二值掩膜：背景候选 = 1
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            if is_bg(px[x, y], ref, spread, tol):
                mp[x, y] = 255

    # 2) 只从上边缘 / 左右边缘取种子（且该点本身是背景候选）
    seeds = []
    for x in range(0, w, max(1, w // 40)):
        if mp[x, 0] == 255:
            seeds.append((x, 0))
    for y in range(0, h, max(1, h // 40)):
        if mp[0, y] == 255:
            seeds.append((0, y))
        if mp[w - 1, y] == 255:
            seeds.append((w - 1, y))
    if not seeds:
        print("    ★ 上边缘没有可用背景种子，跳过")
        return None

    # 3) 在二值掩膜上做 thresh=0 的 floodfill = 取连通域
    for s in seeds:
        if mp[s[0], s[1]] == 255:
            ImageDraw.floodfill(mask, s, 128, thresh=0)

    # 4) 轻膨胀 + 柔化，然后合成纯白
    mask = mask.point(lambda v: 255 if v == 128 else 0)
    mask = mask.filter(ImageFilter.MaxFilter(3))
    mask = mask.filter(ImageFilter.GaussianBlur(0.6))
    white = Image.new("RGB", (w, h), (255, 255, 255))
    img = Image.composite(white, img, mask)

    img.save(out)
    return img, ref


def check(img):
    w, h = img.size
    pts = [(3, 3), (w - 4, 3), (3, h - 4), (w - 4, h - 4),
           (w // 2, 3), (w // 2, h - 4), (3, h // 2), (w - 4, h // 2)]
    return [round(sum(img.getpixel(p)) / 3.0, 1) for p in pts]


def main():
    argv = sys.argv[1:]
    spread, tol = SPREAD, TOL
    for i, a in enumerate(argv):
        if a == "--spread":
            spread = int(argv[i + 1])
        if a == "--tol":
            tol = int(argv[i + 1])
        if a == "--t":                      # 兼容旧参数
            tol = int(argv[i + 1])
    targets = [a for a in argv if not a.startswith("--") and not a.replace("-", "").isdigit()]
    targets = [t for t in targets if not (t.isdigit())]
    if not targets:
        print("用法: python post_whitebg.py <文件或目录> [--spread 14] [--tol 26]")
        return

    files = []
    for t in targets:
        if os.path.isdir(t):
            files += sorted(glob.glob(os.path.join(t, "*成品*.png")))
        elif os.path.isfile(t):
            files.append(t)

    print("纯白背景校正 v2：%d 张（spread=%d tol=%d）\n" % (len(files), spread, tol))
    for f in files:
        if "-白底" in f:
            continue
        base, ext = os.path.splitext(f)
        out = base + "-白底" + ext
        r = fix(f, out, spread, tol)
        if r is None:
            continue
        img, ref = r
        print("  %-42s 背景参考色=%s 边界亮度=%s"
              % (os.path.basename(out), ref, check(img)))
    print("\nOK")


if __name__ == "__main__":
    main()
