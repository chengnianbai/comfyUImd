# 闻灯 · Flux Kontext 作战计划（A 方案）

> 立此文件的原因：**别再开机后才摸索。** 2026-09-17 那天在实例开机状态下硬撞了三轮
> （flux-v1 纯文生图 / flux-v2 三视角 / denoise 阶梯），全部白跑，而豆是按**开机时长**烧的。
> 下次开机的每一步都在下面写死，开机即执行，执行完即关机。

---

## 一、为什么是 Kontext

今日三次实验的硬结论：**从正面基图走 img2img，给不了「同一张脸 + 转头」**。

| denoise | 结果 |
|---|---|
| 0.55 / 0.70 / 0.85 | 四张全是大正面，头根本没转 |
| **0.95** | 转出约 20–30° —— **但人变了**（脸变宽、唇变厚、皮肤变光滑，v23 的瘦长脸和凌乱卷发丢失） |
| 0.85 + guidance 8.0 | 反而更正面、更塑料 → **guidance 不是杠杆** |

根因不是参数，是**能力**：这台机器 `IPAdapter` **0 个节点**、`InstantID`/`PuLID`/`ReActor` 全 0、
`ControlNet` 有节点但**模型目录空**、`clip_vision`/`loras`/`vae`/`text_encoders` 全空。

**Kontext 为什么能解**：它把**参考图的 latent 直接塞进 conditioning**，采样从**纯噪声**开始
（denoise 1.0）。所以姿势、构图、朝向可以大改，人物特征由 conditioning 锁住。
这与 img2img「从原图出发改一点点」是**完全不同的机制**——这才是我们要的东西。

---

## 二、要下的 4 个文件（★ 不是 1 个一体化模型）

服务器上 `text_encoders` 和 `vae` 目录**是空的**，所以这三样必须一起下。

| # | 文件 | 放到 `ComfyUI/models/` 下 | ModelScope 模型 id | 仓库内路径 | 约大小 |
|---|---|---|---|---|---|
| 1 | `flux1-dev-kontext_fp8_scaled.safetensors` | `diffusion_models/` | `Comfy-Org/flux1-kontext-dev_ComfyUI` | `split_files/diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors` | ~11.9 GB |
| 2 | `t5xxl_fp8_e4m3fn_scaled.safetensors` | `text_encoders/` | `comfyanonymous/flux_text_encoders` | `t5xxl_fp8_e4m3fn_scaled.safetensors` | ~4.9 GB |
| 3 | `clip_l.safetensors` | `text_encoders/` | `comfyanonymous/flux_text_encoders` | `clip_l.safetensors` | ~246 MB |
| 4 | `ae.safetensors` | `vae/` | `Comfy-Org/flux1-dev` | `split_files/vae/ae.safetensors` | ~335 MB |

合计 **约 17 GB**（用 `t5xxl_fp16` 会到 ~22GB，所以选 fp8 版）。

> ⚠️ **必须走 ModelScope**。服务器直连 `huggingface.co` 是被墙的，
> Manager 会「跑完但没文件」（`done_count=1` 不代表成功）。
> ⚠️ **Manager 下载不校验完整性** → 下完必须冒烟测试，见第四节。

### 两条下载通道（开机后按盘点结果二选一）

**通道 A —— 让服务器自己下（首选，无需你操作）**

```bash
python _scripts/kontext_setup.py download
```

**通道 B —— 你在服务器的终端里手动跑（通道 A 不灵时用）**

```bash
modelscope download --model Comfy-Org/flux1-kontext-dev_ComfyUI \
  split_files/diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors \
  --local_dir /models/diffusion_models/

modelscope download --model comfyanonymous/flux_text_encoders \
  t5xxl_fp8_e4m3fn_scaled.safetensors clip_l.safetensors \
  --local_dir /models/text_encoders/

modelscope download --model Comfy-Org/flux1-dev \
  split_files/vae/ae.safetensors --local_dir /models/vae/
```

---

## 三、开机后的执行顺序 —— **已合并成一条命令**

> ★ 2026-09-18 修订（重要）：**「夜市百相簿」是主工作流**。
> 之前每加一种能力（Flux 质感 / 迭代转头 / Kontext 转头）都在旁边新建一个文件，散成了 4 个，
> 这条做法已废弃。现在**只有 `夜市百相簿.json` 一个文件**，内部按角色分区：
>
> | 分组 | 内容 | 底模 |
> |---|---|---|
> | 【闻灯】立绘 · SDXL 白底 | **原有的 24 个节点，id 一律未动** | SDXL |
> | 【闻灯】脸部 · SDXL img2img 保身份 | v23 的做法（**无第二段重绘**） | **SDXL** |
> | 【闻灯】转头 · Flux Kontext 90° | 左90 / 右90 / 左45 | Flux Kontext |
>
> 合并后共 **72 节点 / 96 链接 / 7 个 SaveImage / 3 组**。
> 装配由 `_scripts/build_master_wf.py` 负责，**原工作流 id 保留**（`8f3eed13-…`），
> 所以你在浏览器里打开的仍然是同一个「夜市百相簿」。
>
> ★★ **3 组 ≠ 3 个模型**：立绘与脸部**同为 SDXL**（脸部就是 v23 那条 img2img 线），
> 只有「转头」用 Flux —— 因为 **SDXL 转不动头**（已四次实证）。**Flux 只做 SDXL 做不到的事。**
>
> ★★ **「Flux 质感对照 A~E」组已于 2026-09-18 删除**。理由是可判定的：免费证据显示
> flux-v2 去掉重绘后**发丝能追平 v23、但皮肤仍偏滑** → 最好的结果也只是「接近 v23 但不如」，
> 没有跑的价值。**闻灯的主力是 SDXL，Flux 不是。**

开机只做一件事 —— 双击项目根目录的：

| 入口 | 做什么 | 耗时 |
|---|---|---|
| **`快出图-不下载.bat`** | 只出图 **1 张**（闻灯脸部正面，SDXL img2img 无重绘） | **2~4 分钟** |
| **`开机一键.bat`** | 全流程：出图 + 下 Kontext 17GB + 转头 3 张 | 20~30 分钟 |
| `状态查询.bat` | 只读：看实例状态、本地验证（**不烧豆**） | 10 秒 |

等价的命令行：

```
python _scripts/oneshot.py quick     # 快路径：只出图
python _scripts/oneshot.py all       # 全流程
```

`oneshot.py all` 的编排内容，以及各步单独重跑的子命令：

| 阶段 | 内容 | 单独跑 | 耗时 |
|---|---|---|---|
| 0 | 等实例上线（15 秒探一次，最多 25 分钟） | `oneshot.py wait` | — |
| 1 | **盘点** GPU / 节点 / 模型落地 / 磁盘余量 | `oneshot.py p1` | 10 秒 |
| 2 | **装配**主工作流 → **上传身份基图** → 推送 → 本地验证 | `oneshot.py p2` | ~30 秒 |
| 3 | **出图** 1 张（脸部正面）→ 自动拼 1:1 对比图，**同时后台开始下 Kontext** | `oneshot.py p3` | ~2 分 |
| 4 | **校验**四件套完整性 → **转头 3 张**（左90/右90/左45） | `oneshot.py p4` | ~2 分 |
| 5 | **报告** + 收尾检查清单 | `oneshot.py report` | 5 秒 |

★ **第 3 步把「出图」和「下载」并行**：下载走网络、出图走 GPU，互不冲突，
  省掉原来串行等待的十几分钟。

★ **第 2 步的顺序不能颠倒**：必须**先上传身份基图再推工作流**。
  `LoadImage` 的 widget 值只是一个文件名，工作流 JSON 里不带图片数据；
  实例重建后 `input/` 是空的，两个块（脸部 / Kontext）会一起报 `invalid image file`。
  脚本已把「上传 → 回读确认 → 才推送」做成硬顺序，传不上去就**不推**。

★ 全程结束后 `report` 会打印收尾清单 —— **确认完立刻关机**。

### ⚠️ 合并后有一个必须知道的副作用

主工作流里有 **17 个 `SaveImage`**。**在浏览器里点「运行」会把 17 条分支全部跑一遍**
（几十分钟，全是豆）。所以：

- **跑图一律用 `run_wf.py` 按分支名提交**（`oneshot.py` 已经这么做）；
- 浏览器**只用来看结构**，或者选中某个输出节点按 `Ctrl+Enter` 只跑那一条。
- 另有 2 个 `SaveImage` 属于**白底立绘块**，不列入自动跑（要用时在浏览器手动点）。

### 重跑是幂等的

`build_master_wf.py --fetch` 会先拉服务器现行版作基线。**如果你在浏览器里改过主工作流，
必须用 `--fetch` 重新装配**，否则你的改动会被覆盖。

同时脚本有**防重入守卫**：万一 `oneshot.py all` 跑了两遍，第二遍 `--fetch` 拉回来的会是
已经合并的 128 节点版 —— 守卫会识别出来，按「立绘」分组的包围盒**自动还原成原来那 24 节点**
再装配，不会把节点复制成 232 个。这一步有独立自检：

```bash
python _scripts/build_master_wf.py --selftest    # 128 节点 → 还原 → 24 节点，与基线比对
python _scripts/verify_master.py                 # 17 条分支依赖 + 两条跑图命令能否选中目标
```

---

## 四、Kontext 参数与提示词要点（与 SDXL / Flux-dev **都不通用**）

- **cfg 必须 1.0**；`FluxGuidance` 取 **2.5–4.0**（编辑任务偏低更稳）。
- **正脸和唯一的侧脸采样都使用 denoise 1.0 + 纯噪声 latent** —— 参考图只通过
  `ReferenceLatent` 进入 conditioning。旧版正脸 `denoise 0.35` 实测几乎复制 SDXL 原图，已撤销。
- **输出尺寸随参考图**（`FluxKontextImageScale` → 16 的倍数），别自己写 1024×1280。
- 节点链路：`UNETLoader` + `DualCLIPLoader` + `VAELoader` → `LoadImage` → `FluxKontextImageScale`
  → `VAEEncode` → `ReferenceLatent`（接在正向 conditioning 后）→ `KSampler`(denoise 1.0)
  → `VAEDecode` → `SaveImage`；负向用 `ConditioningZeroOut`。
- ★ **提示词写成「编辑指令」，不是画面描述**。不要写「a photo of a man with...」，
  而是写「**Turn his head to a full 90-degree left profile. Keep the same person, the same
  messy wavy black hair, the same skin texture, the same lighting and background.**」
- ★ **一轮只改一件事**（这次只改朝向），改多了它会把人物也一起改掉。
- ⚠️ Dev 版对有些提示词**可能完全不编辑**（官方明说的短板）→ 不生效就换措辞，
  例如加「Change the camera angle so we see him from his left side.」

### 当前三视角链路

```text
00009（SDXL 确认图）
        ↓
Kontext 统一正脸（d1.0 + 纯噪声）
        ↓
一张鼻尖朝画面左的侧脸（d1.0 + 纯噪声）
        ├─ 原图保存为左向侧脸
        └─ ImageFlip 水平翻转为右向侧脸
```

旧版让两个 Kontext 分支分别理解 `LEFT/RIGHT`，实测两张都生成鼻尖朝画面左；现在只让模型生成
一个方向，反方向由像素级水平翻转硬保证。两张侧脸因此具有完全相同的纹理、光影、色彩和颗粒。
注意：翻转也会交换痣等左右不对称特征的位置，三视角确认时需要单独检查眼尾痣是否满足后续视频要求。

一次提交三个成品，确保统一正脸也落盘：

```bash
python _scripts/run_wf.py "夜市百相簿-主工作流.json" "闻灯Kontext统一正脸,闻灯主图-左侧脸,闻灯主图-右侧脸" final
```

**冒烟测试判据**：出一张真的**转过头的**、且**还是同一个人**的图。
两者缺一即为失败 → 不要继续往下跑，先回来调提示词。

---

## 五、收尾

- 产物统一落盘到 `系列-夜市百相簿\02-角色\闻灯\设定图\主工作流\`（原先按分支分目录，现已合并）。
  自动拼好的对比图：`系列-夜市百相簿\02-角色\闻灯\设定图\_1比1_脸部_主工作流.png`、`_1比1_头发_主工作流.png`、
  `_对比_Kontext转头.png`。**判断质感只认 1:1 裁切图**（整图缩放会把毛孔和发丝抹平）。
- 工作流写在实例磁盘上，本地备份（全部在 `_scripts\_wf\`）：

  | 文件 | 说明 |
  |---|---|
  | `夜市百相簿_主工作流.json` | ★ 装配产物，128 节点，丢了可原样重推 |
  | `夜市百相簿_v19.json` | 装配基线（原 24 节点），**别删，守卫依赖它** |
  | `server_夜市百相簿_原始.json` | 最早从服务器拉回来的原始版 |
  | `闻灯-Flux-质感修复对照.json` / `闻灯-Kontext转头.json` | 两个区块的独立构建产物 |
  | `闻灯-Flux脸部三视角.json` / `-迭代转头.json` | 旧散装版，仅作历史归档 |

- ★★ **确认完立刻关机**。豆按开机时长烧，与是否在跑图无关。
  2026-09-17 那天开机 6.83 小时，真正生成只占十几分钟 —— 95% 的钱花在空转。

---

## 附：若 A 方案仍不达标，退路

- **B**：下 SDXL OpenPose ControlNet（~2.5GB，节点已就位、无需重启）——便宜快，
  但要我手绘侧头骨架，效果要撞，且质感退回 SDXL。
- **C**：零成本，左右侧脸用已确认的正面脸**镜像**——数学上保证同一人，但不是真 90°。
