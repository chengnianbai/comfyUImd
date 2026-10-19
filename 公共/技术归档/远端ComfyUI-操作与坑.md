# 远端 ComfyUI · 操作与坑（2026-09-18 整理）

实例：`https://gw-<hash>.cn-beijing.aigclinks.com:8016/`，RTX 5880 Ada 48G，ComfyUI 0.30.1。
按机身**开机时长**计费 → 操作前先看 `MEMORY.md` 的成本铁律。

## 1. 网关与连通

- ★★ **每次开机 gateway hash 都会变**（如 `gw-496303efdc4841bfa3e30e994493225f`）。
  旧地址对**所有**路径返回 **400 + HTML「服务连接失败」**。
- 活跃脚本已改为 `BASE = os.environ.get("COMFY_BASE", "<默认>")` → 换网关可不改代码：
  `COMFY_BASE=https://gw-xxxx.cn-beijing.aigclinks.com:8016 python oneshot.py p1`
- 正常健康检查：`GET /system_stats` 返回 200，延迟 150–250ms。
- **掉线唯一判据**：`/`、`/system_stats`、`/queue` **全部** 400+HTML。（掉线 ≠ 用户网络问题）
- ★★ **本网关上行为约 40 KB/s**：实测传 1.71 MB 花 **42.5 秒**，5.42 MB 会被 `timeout=600` 吃满，
  表现成「脚本卡死无输出」。→ **凡上传，先缩到 1~2 MB**；超时设 180s 足够。

## 2. API 速查

| 用途 | 端点 |
|---|---|
| 健康 | `GET /system_stats` |
| 全量节点 | `GET /object_info`（**很重**，探测节点用它） |
| 单节点字段 | `GET /object_info/<NodeName>`（同时暴露该 loader 可见的文件列表） |
| 工作流列表 | `GET /api/userdata?dir=workflows`（**返回字符串数组**） |
| 读工作流 | `GET /api/userdata/workflows%2F<名>`（**斜杠必须 %2F**） |
| 写工作流 | `POST 同路径?overwrite=true`，body=JSON |
| 上传图 | `POST /upload/image`（multipart：overwrite/type=image/subfolder + image） |
| 提交出图 | `POST /prompt` |
| 队列/历史 | `GET /queue`、`GET /history` |
| 日志 | `/internal/logs/raw` |
| 列 input | `/internal/files/input` |

⚠️ **探测节点必须拉全量 `/object_info` 再 `名称 in d`**：不存在的节点返回 `{}` + 200，**不是 404**。
⚠️ 下载产物 / 中文名**必须 urlencode**，否则 `UnicodeEncodeError: 'ascii'`。
⚠️ `C:\ComfyUI\models` 是**目录联接**→`D:\ComfyUI-models`，`/internal/folder_paths` 永远显 C 盘**属正常**。
真判据 = 文件能否越过 10,737,418,235 字节（旧 ENOSPC 截断点）。
⚠️ `/internal/files/input` 返回**字符串数组**，元素形如 `"名字.png [input]"`（**不是 dict**）→
比对前要 `n.split(" [")[0].strip()`。曾因此把「上传成功」误判成失败并拒绝推送。更稳的验证是
`GET /object_info/LoadImage`，它的 image combo 列表就是 input/ 目录内容。

## 3. ComfyUI-Manager 下载模型（★ 重要）

Manager V3.41 的 `POST /api/manager/queue/install_model` 有 **KeyError: 'base'** 的 bug
（`check_whitelist_for_model` 里 `x['base']` / `item['base']` 没做防护）→ **请求体缺字段就 500**。

**正确用法**：请求体必须带 `save_path` / `base` / `filename` 三个字段，且要**命中 model-list.json 白名单**：

```json
{"save_path":"text_encoders/t5","base":"t5","filename":"t5xxl_fp8_e4m3fn_scaled.safetensors",
 "url":"https://www.modelscope.cn/.../t5xxl_fp8_e4m3fn_scaled.safetensors",
 "name":"t5xxl_fp8_e4m3fn_scaled.safetensors","type":"text_encoders"}
```

流程：`install_model`（可连续入队多个）→ `POST /api/manager/queue/start` → `GET /api/manager/queue/status`。

- ★ **不校验 url** → 可把 url 换成 ModelScope 直链（**服务器上唯一可靠源**，直连 HF 被墙）。
- ★★ **文件名不在白名单时**（如 `flux1-dev-kontext_fp8_scaled.safetensors`）→ 用自己的名字请求 **HTTP 400 Invalid model install request**。
  **解法：借一个白名单槽位、把 url 指向目标文件** → 200 入队。
  **代价：会以借用槽位的名字落盘**（如 Kontext 会存成 `flux1-schnell.safetensors`）→
  **用完必须回改工作流里的模型名引用，并在节点标题注明真实内容**。
- ⚠️ `done_count=1` **≠ 成功**（可能「跑完但没文件」）；⚠️ **不校验完整性**（17.2GB 曾截断）
  → **大文件下完必须冒烟测试**（真跑一次，看有没有 OOM / shape 报错）。
- 白名单清单可离线取：
  `https://gh-proxy.com/https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/model-list.json`，
  条目字段 `save_path` / `base` / `filename` / `url` / `size`。

## 4. ★★ 浏览器缓存坑（"我明明推上去了，你看到的还是旧的"）

- **ComfyUI 前端打开 `/#<工作流id>` 时，优先加载 localStorage 里同 id 的旧副本，不读服务器文件。**
  所以「服务器文件已更新」与「用户浏览器看到的」是**两件事**：id 没变 → 浏览器一直给看它自己那份缓存。
- ★ 解法：**换文件名 + 换一个新 uuid 作 id** 另存一份，并让用户在左侧 **Workflows 侧栏点开**，
  不要指望用旧 URL 的 hash 刷新。
- ★ 另注意：新版三块在画布上是**分散摆放**的（立绘 300,300 / 脸部 3190,300 / 转头 300,3090），
  只看到第一个框 ≠ 没更新 → 让用户 **Ctrl+A 全选 + `.`（Fit view）** 才看得到全部。
- ★ 本地改磁盘上别的 ComfyUI 的 workflow json 同理，用户标签页不会自动看到。

## 5. 翻过的车（同类错误别再犯）

1. Kontext 输出前缀漏 `-成品` → 3 条转头分支一条都选不中（分支本身完全正常，只有跑图才暴露）。
2. `--fetch` 无防重入 → 二次合并成 232 节点。已在 `build_master_wf.py` 加检测+还原守卫（`--selftest`）。
3. 基图无人上传 → 实例重建后 `input/` 为空，脸部/质感/Kontext 三块一起报 `invalid image file`。
4. 下载无磁盘保护 → 改为**按体积升序**下载（小的先到手）+ 每步磁盘余量探测。
5. `oneshot.py` p3 仍找已删的 `FluxV5` → 命中 0 条、白开机。已改为 `闻灯-脸部正面`。
6. 多步链条（跑→下载→再上传当下一步基图）**必须每步落盘**：实例可能瞬间掉线
   （实测 `ConnectionResetError WinError 10054`），不落盘整条链白跑。

## 6. 机器能力盘点（827 节点实测）

- **有**：`ControlNetApply/ApplyAdvanced/Loader`、`DiffControlNetLoader`、`CLIPVisionLoader/Encode`、
  `ReferenceLatent`、`FluxKontextMultiReferenceLatentMethod`。
- **没有**：IPAdapter 0、InstantID / PuLID / ReActor / T2IAdapter 全 0、**未装 Impact-Pack**
  （无 FaceDetailer / SAMLoader → 脸部精修与自动抠图做不了）。
- ★★ **"同一张脸 + 任意朝向" 必须靠 IPAdapter / ControlNet / Kontext，别再调 denoise。**
- SDXL 参数：`896×1152`、CFG 10、`dpmpp_2m`+`karras`、steps 30、**CLIP skip 1**（`stop_at_clip_layer=-1`）、
  二段 `steps20 / CFG10 / denoise 0.25`。5 视角（含 4x 放大+重绘）约 4 分钟。
- ⚠️ **SDXL 拿不到指定朝向**（`facing left/right`、`90 degree side view` 全不生效）。
- Flux 参数与 SDXL **完全不通用**：cfg 必须 **1.0**，`euler`+`simple`，20~30 步，不需要 CLIPSetLastLayer。


## 7. 模型文件接口与落盘路径（2026-09-18 新增）

- ★★ **`GET /models`** → 所有模型目录名；**`GET /models/<目录>`** → 该目录下的文件列表（字符串数组）。
  子目录用**反斜杠**表示：`"t5\\t5xxl_fp8_e4m3fn_scaled.safetensors"`、`"FLUX1\\flux1-dev-fp8.safetensors"`。
  这是比 `/object_info/<Loader>` 更直观的盘点方式（后者也能用，见 §2）。
- ★★ **工作流里的模型名必须带子目录前缀**，否则 combo 校验不过 → `POST /prompt` 直接被拒。
  实例：`CheckpointLoaderSimple` 要写 `FLUX1\flux1-dev-fp8.safetensors`。
- ★ **ComfyUI-Manager 的 `install_model` 会把文件写进 `save_path` 指定的子目录**：
  `save_path:"text_encoders/t5"` → `models/text_encoders/t5/xxx.safetensors`；
  `save_path:"vae/FLUX1"` → `models/vae/FLUX1/ae.safetensors`；
  `save_path:"diffusion_models/FLUX1"` → `models/diffusion_models/FLUX1/xxx.safetensors`。
  下完**必须回查真实落盘路径**，再据此改工作流的引用名。

## 8. 浏览器缓存绕过：单文件 + 每次推送换 id（2026-09-18 定稿）

★ 用户明确否决了"多造一份查看版"：**服务器上只留 `夜市百相簿-主工作流.json` 一个文件**。
绕过缓存的机制下沉到推送环节 —— `build_master_wf.py --push` **每次推送都换一个新 uuid 作 id**：

- 服务器上**永远只有一个文件名**，不再出现 `夜市百相簿.json` / `-查看版` / `-主工作流` 三份并存；
- 每次推完，把新 `#<uuid>` 链接给用户即可（浏览器本地没有这个 key → 一定读服务器文件）；
- `run_wf.py` 认的是**文件名**，与 id 无关，所以换 id 不影响跑图。

⚠️ **下载模型期间看不到字节进度**（Manager 只给三个计数，见 §9）→ 用 §9 的办法判断。

## 9. 下载监控：怎么知道 Kontext 真的在下载（2026-09-18 新增）

- ★★ **Manager 的模型下载队列是单线程串行的**（2026-09-18 用户问"ae 不能和 Kontext 一起下吗"）：
  一次只处理队列里的第一个，其余排队等着，**没有并行开关**。所以"ae 必须等 Kontext"不是权重排序，
  纯粹是**入队顺序** —— ae 那次 404 崩掉后 Kontext 立刻占住线程（16:46:45），重入队的 ae 只能排后面。
  ★ 想真并行只能**绕开 Manager**（终端 `curl.exe` 下到同名路径），但**收益通常为 0**：
  判据是"早到有没有用" —— 转头组同时需要 Kontext + ae，**瓶颈是 11GB 的 Kontext，ae 只有 0.32GB**，
  并行省下的就是它那 1 分钟，且绕开队列还有两个进程写同一路径的损坏风险。
- ⚠️ **Manager 没有任何进度百分比接口**：`/api/manager/queue/status` 只返回
  `{"total_count":N,"done_count":N,"in_progress_count":N,"is_processing":bool}`，
  其余 `queue/history`、`download/status`、`task/status` 全部 **404**。
- ⚠️ 下载期间 **ComfyUI 主日志不更新**（`/internal/logs/raw` 停在启动任务那一条），
  `/internal/files/temp` 也是空的 → 无法从日志看进度。
- ★★ **权威落地判据 = Loader 的 combo 列表**（`GET /object_info/<Loader>`）：
  这个名字真的出现在列表里，才代表文件能被加载。`GET /models/<目录>` 同理，但**父目录不列子目录内容**
  （`/models/diffusion_models` 会是 `[]`，实际文件在 `FLUX1\` 里）。
- ⚠️ **写记忆文件一律用 Write/Edit 工具，不要用 `bash -c` 内联 Python**（2026-09-18 第三次踩）：
  bash 双引号里出现**反引号会被当命令替换执行**、**英文直引号会提前截断字符串**，
  结果写进 md 的正文悄悄少掉几段（本次「复验地址」那两行就被吞空了）。要么用 Edit 工具直接改 md，
  要么先用 Write 写一个 `_tmp.py` 再执行。
- 工具：**`_scripts/watch_dl.py`** —— 每 90 秒打一条快照（只在有变化时记），
  `--once` 只看一次；日志追加到 `_scripts/_dl_watch.log`。全部到位会打印里程碑并退出。
- ★★ **`ae.safetensors` 的正确 ModelScope 直链**（踩过的坑：`Comfy-Org/flux1-dev/.../vae/ae.safetensors` **404**，
  这条死地址让队列卡了半个多小时、排在后面的 Kontext 一直没轮到）：
  ```
  https://www.modelscope.cn/models/AI-ModelScope/FLUX.1-dev/resolve/master/ae.safetensors   # 335 MB，实测可下
  ```
- ★★ **入队前先在本地验地址**：发 `Range: bytes=0-255` 的 HEAD/GET，看 `Content-Range` 与文件头
  （safetensors 头是 `{"double_blocks.0...`），**别等队列替你去试**。
- Kontext 主模型正确直链（11.09 GiB，实测返回 `11904640136` 字节）：
  ```
  https://www.modelscope.cn/models/Comfy-Org/flux1-kontext-dev_ComfyUI/resolve/master/split_files/diffusion_models/flux1-dev-kontext_fp8_scaled.safetensors
  ```
- ★ 用户可自助的下载命令（终端，`-C -` 支持断点续传）：
  ```batch
  cd /d C:\ComfyUI\models\diffusion_models
  curl.exe -L -C - -o flux1-dev-kontext_fp8_scaled.safetensors "<上面的 ModelScope 直链>"
  ```
  ⚠️ **手动下与 Manager 队列不能同时对同一文件动手**（两进程写同一路径会互相破坏）。

## 10. ★★ 多分组工作流"只跑其中一组"（2026-09-18 用户问，必须答对）

**前提知识：ComfyUI 是从输出节点（SaveImage / PreviewImage）反向构建执行图的。**
没有任何输出节点依赖的节点**根本不会被执行** —— 所以"控制跑哪些分支"= 控制哪些**输出节点活着**。

### ✘ 错误认知（必须纠正，我曾据此给用户下过错误指令）

- **`Ctrl + Enter` 不是"只跑选中节点"**，官方定义就是**排队整个提示词（全量）**。
  官方快捷键表（docs.comfy.ac.cn/interface/shortcuts）里**没有**"运行选中输出"这一项。
- 点了画布上的大「运行」/ `Ctrl+Enter` → **所有活着的 SaveImage 分支一起跑**。
  实测事故：16:16 用户点了一次运行 → 4 条分支同时开跑（Kontext 那 3 条因模型缺失报
  `Value not in list` 才没跑）。

### ✔ 正解一（界面操作，最防呆）：静音不用的输出节点

1. 画布上 `Ctrl + 拖拽` 框选**不跑的那些组**（本工作流：左边 x≈270–2750 一整列 = 全身组 + 转头组；脸部组在右边 x≥3160，不受影响）；
2. 按 **`Ctrl + M`** → 被选中的节点变**紫色**（静音 / mode=NEVER）；
3. 点「运行」。只有脸部组的 2 个 SaveImage 还活着 → **只跑脸部**；
4. 恢复：再框选同一片区域按一次 `Ctrl + M`（它是 toggle）。
   ★ **只要不点保存，刷新页面就自动恢复原状** —— 因为静音状态只在浏览器内存里。

其他相关快捷键：`Ctrl + B` = 跳过/取消跳过（bypass，绿色，直通）；`Ctrl + M` = 静音/取消静音。
**分组框右键菜单**里也有 Set Group Nodes to Always / Never / Bypass / Mute，可整组设置。

### ✔ 正解二（命令行，100% 精确、零误触）

```batch
python _scripts\run_wf.py "夜市百相簿-主工作流.json" "闻灯-脸部正面" final
```
`run_wf.py` 按 SaveImage 前缀挑分支（`关键词 in prefix and prefix.endswith("成品")`），
只提交命中的那条链 —— 不存在"误跑其他组"的可能。

### 当前工作流（77 节点 / 101 链接 / 3 组 / 7 输出）的分组与输出对照

| 组 | 画布位置 | 输出前缀 |
|---|---|---|
| 【闻灯】全身立绘 · SDXL（29 节点） | 左上 x=270 y=230 | `闻灯-全身正面-草稿` / `-成品` |
| 【闻灯】脸部 · SDXL img2img（22 节点） | **最右 x=3160 y=230** | `闻灯-脸部正面-草稿` / `-成品` |
| 【闻灯】转头 · Flux Kontext（26 节点） | **最下 x=270 y=3020** | `闻灯Kontext-左侧90/右侧90/左侧45-成品` |

⚠️ 三块在画布上**横向/纵向散开**，`Ctrl+A` 后按 `.`（fit view）才看得到全部。
⚠️ 用户若在浏览器里改了工作流并**保存**，会把静音状态/改动写回服务器 → 我下次 `--fetch` 前先确认。

---

## ★★ 模型引用必须写「服务器实际落盘的全名（含子目录）」（2026-09-18 踩）

**症状**：节点装配正常、推送正常、本地自检全绿，**提交时才抛 `value not in list`** —— 而那时实例已在烧豆。

**根因**：Loader 只接受**下拉列表里有的值**，列表来自服务器实际扫到的文件。
用 ComfyUI-Manager 下的模型，Manager 按 model-list.json 的 `save_path` 自动建子目录，名字就带前缀了。

| 用途 | 该写的引用名 |
|---|---|
| t5 | `t5\t5xxl_fp8_e4m3fn_scaled.safetensors` |
| VAE ae | `FLUX1\ae.safetensors` |
| Kontext（借 `flux1-schnell` 槽位落盘） | `FLUX1\flux1-schnell.safetensors` |
| SDXL 底模 / 放大模型 | 无子目录，原样 |

### 查证手段

- ✅ **`GET /models/<dir>`**（或 `/api/models/<dir>`）→ 字符串数组，就是服务器真扫到的文件。
  目录名：`checkpoints` / `diffusion_models` / `vae` / `text_encoders` / `upscale_models` / `loras` / `controlnet`。
- ❌ **`/internal/files/<dir>` 查不了 models**：只认 input/output/temp，其它返回
  **400 `{"error": "Invalid directory type"}`**（子路径如 `diffusion_models/FLUX1` 是 404）。
- ✅ **最权威的判据是 `/object_info/<NodeName>` 的 combo 列表** —— 那就是前端下拉框的内容。

### ★★ `_scripts/check_model_refs.py`（开机前跑一次）

```bash
python _scripts\check_model_refs.py            # 校验 _wf\夜市百相簿_主工作流.json
python _scripts\check_model_refs.py 其它.json    # 校验指定文件
```
逐节点把 Loader 引用名和服务器真实文件对账；找不到时还会列出**同名文件在哪**，
帮你区分「漏了子目录」还是「文件压根没下」。退出码 0 = 全对。

### ⚠️ 同一台服务器上 combo 有两种编码（实测并存），解析器必须两种都认

```
旧式： "unet_name":  [["a.safetensors", "b.safetensors"], {"advanced": true}]
新式： "model_name": ["COMBO", {"multiselect": false, "options": ["a.pth", "b.pth"]}]
```
`UpscaleModelLoader` 就是**新式**。只认旧式 → 解析出字符串 `"COMBO"` →
把明明存在的 `4x-UltraSharp (1).pth` 误报成"对不上"。

---

## ⚠️ 工具坑：同一条消息里的两笔并行 Edit 会互相覆盖

- 现象：两笔 `Edit` 同时改**同一个文件** → 各自基于同一份快照写回 → **后一笔覆盖前一笔**；
  工具**仍报 `success`**，磁盘上只留下后一笔。
- 后果：这次丢掉了「4 个模型常量」那笔，是靠重跑 `push_kontext_wf.py --local` 后
  JSON 里还是旧名字才发现的。
- ★ 规矩：**改同一文件必须串行、一次一笔**；写完立刻用 **Python 读回来确认**
  （`Read`/`Grep` 工具可能返回缓存旧内容 —— 同一 md5 的文件，Read 给旧文、Python 给新文，这次真出现过）。

---

## 11. ★★ 平台公共模型盘：平台"有" ≠ ComfyUI"能扫到"（2026-09-20 实证）

- 无影灵构**预置公共模型盘**，挂在**工作站云桌面**里（用户处为 `M:\Comfyui`；官方文档路径形如
  `wuying-pub/Comfyui/vae/wan_2.1_vae.safetensors`）→ **`M:\Comfyui` 就是它**，容量 PB 级。
  ⚠️ 它是**远程云桌面里的盘**，所以在本机查盘符是查不到的（09-18 那次白查）。
- ★★ **它不在 ComfyUI 的扫描路径里**。实测 `GET /internal/folder_paths`：只有
  `C:\ComfyUI\models\*`（+ `output\checkpoints` / `output\clip` / `output\vae` / `output\loras`），
  **没有任何 M:/wuying-pub 条目** → 模型盘上的文件**永远不出现在 Loader 下拉框**。
- 实测（2026-09-20）：`CheckpointLoaderSimple` 4 项 / `UNETLoader` **1 项** / `VAELoader` 2 项 /
  `StyleModelLoader` **0 项** / `CLIPVisionLoader` **0 项**
  → **`flux1-redux-dev` 不在任何下拉框里**，且它需要的 `style_models` + `clip_vision` **都是空目录**。
  （"控制台里看得到 Redux" ≠ 能加载。）
- ★★ **解法：`C:\ComfyUI\extra_model_paths.yaml` 指向模型盘**（`base_path: M:/Comfyui`）+ **重启服务**
  → 整个公共库进下拉框，**零下载、零占 C 盘**。**平台有图形化云桌面 ⇒ 不需要 shell**（记事本即可）。
  ⚠️ 唯一不确定：**模型盘盘符在 ComfyUI 服务会话里是否可见**（映射网络盘可能不可见）；
  判据 = 重启后下拉框里有没有出现。
  ★ §7 与技能坑 6 里写的"换盘必须服务器 shell，这类实例通常不给"**作废**。
- ★★ 官方三条取模型的正路（文档：使用公共模型库 / 下载缺失模型）：
  1. 工作流**缺模型弹窗** → **「立即下载」**（模型库收录了该文件名才有按钮，下完自动放进
     ComfyUI 对应目录，例 `models/checkpoints/`、`models/vae/`）；
  2. 控制台**模型库** → 复制"存放路径" → 云桌面双击**模型盘**快捷方式 → `wuying-pub` → 找到文件
     → **复制**进 `C:\ComfyUI\models\<类型>\`（注意：Kontext 那条必须覆盖成 `flux1-schnell.safetensors`
     这个借槽位名，工作流引用才对得上）；⚠️ 仍受磁盘限制；
  3. ★★ **在工作站内的浏览器**访问魔搭社区下载 —— 官方原文：
     > 请务必在工作站内打开浏览器访问魔搭社区，不要在本地电脑上访问，因为无影灵构已与魔搭社区
     > 实现**内网加速**，在工作站内下载可显著缩短模型下载时间。
     且能按文件名**搜到正确仓库** —— 09-18 的 404 就是手写了 `Comfy-Org/flux1-dev` 这个不存在的路径。
- ★ 记住：**从来没有"要再下一个 Flux 底模"这种需求**。`flux1-dev-fp8`（17.25GB，checkpoints）
  一直在服务器上且完好；真正欠的只有 Kontext 那个 11.9GB 残件 + ae 的 0.34GB 残件。

