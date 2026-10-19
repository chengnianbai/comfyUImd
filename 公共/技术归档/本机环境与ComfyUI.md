# 本机环境 / 网络 / ComfyUI 工作流（细节归档）

> 本文件是 `MEMORY.md` 的细节归档，MEMORY.md 只留最关键的规则。

## 本机硬件与系统

| 项目 | 值 |
|---|---|
| OS | Windows 10.0.19045（win32） |
| shell | 精简版 PortableGit bash，**缺 coreutils**（无 ls/head/dirname/df），`cmd /c` 也会挂 → 文件与命令操作优先用 Python 绝对路径 |
| 显卡 | NVIDIA GTX 750，**显存 1GB**，算力 sm_50（Maxwell 2014），驱动 577.00 |
| CPU | Intel i5-10400F，6 核 12 线程 |
| 内存 | 32GB |
| Python | 系统 3.13.7（`C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe`）；托管 3.13.12（`C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe`）← 本会话可用 |
| 磁盘 | C 盘紧张（曾低至 6.8GB），D 盘充裕 → **大文件一律装 D 盘** |

### 显卡结论（勿重复踩坑）
- PyTorch 2.8+ 的 cu128/cu129、以及全部 CUDA 13.x 已移除 Maxwell/Pascal（sm_50/sm_60）。
- GTX 750 显存 1GB，跑 SD 类模型会换页，性能反而不如 CPU → **本机推理默认走 CPU**。

## 国内网络环境（装依赖踩坑）

- **GitHub 直连**：TCP 通但传输卡死（4 分钟 0.2KB）。代理：
  `https://gh-proxy.com/https://github.com/<user>/<repo>.git`（5.8MB/s）；备选 `https://ghfast.top/`（1.2MB/s）。
- **PyPI 镜像**：
  - 清华 `pypi.tuna.tsinghua.edu.cn` → **403**，不要用。
  - 阿里云 `mirrors.aliyun.com/pypi/simple` → 可用但**版本滞后**（曾缺 `comfyui-workflow-templates==0.11.60`）。
  - **首选 USTC `mirrors.ustc.edu.cn/pypi/simple`**，备选腾讯云 `mirrors.cloud.tencent.com/pypi/simple`。
- **HuggingFace**：直连不通。必须走 **`hf-mirror.com`**（实测 7.7MB/s，偶发瞬时 502，重试即可）；
  备选 `aifasthub.com`。Civitai 上的模型先查 HF 有无镜像（`digiplay/` `stablediffusionapi/` 等组织大量镜像；
  HF `api/models?search=xxx` 可列全部同名仓库）。
- **Civitai 直连**：被代理拦（502），本机下不了。
- **gh-proxy / ghfast / ghproxy.net**：只适合小文件，**会拦截 HF 的 LFS 大文件跳转**
  （`Redirect to a disallowed URL was blocked`），2GB 级模型必失败。
- **魔搭 modelscope.cn**：API 与文件下载通（`/api/v1/models/{ns}/{name}/repo?Revision=master&FilePath=x`），
  但**无可用搜索 API**（`/api/v1/models?...` 全 404），只能靠已知仓库名。
- ⚠️ **本机绕过代理直连一律超时**（WinError 10060，运营商层屏蔽）。脚本**不要** `ProxyHandler({})`，
  直接用环境注入的代理；`dangerouslyDisableSandbox` 也**不会**移除已注入的代理变量。

## 本地 ComfyUI

路径 `D:\xiaobai-claude code\ComfyUI`，独立 venv，CPU 版，端口 8188，文档入口 `从这里开始.txt`。
- 启动 `启动ComfyUI.bat`（端口占用检测 + 自动开浏览器）；停止 `停止ComfyUI.bat`；
  8188 占着关不掉时用 `启动ComfyUI-换端口.bat`（8189）。
- 模型：SD 1.5（`v1-5-pruned-emaonly-fp16`）、SD-Turbo、`majicmixRealistic_v7.safetensors`（2034MB，亚洲人像向）、备用 VAE。
  - ⚠️ **代次不同**：`v1-5-pruned-emaonly-fp16` = SD 1.5；`sd_turbo` 底子是 **SD 2.1**
    → SD 1.5 的 LoRA 只能挂前者，**挂不上 SD-Turbo**。
  - 官方 SD 1.5 底模默认出欧美脸；要亚洲脸须换底模（majicMIX realistic / ChilloutMix / 国风3）。
- 插件：自建 `custom_nodes\ComfyUI-Cangyuan`（沧元算力远程出图/出视频）；
  第三方 `custom_nodes\ComfyUI-Yvtou-Gemini`（节点 `LinkAPIGeminiImage`，支持自定义 base_url，可接中转站）。
- 九个工作流在 `user\default\workflows\`：本地 SD-Turbo / 本地 SD1.5 / 本地出图-亚洲人像 /
  本地出图-亚洲人像-质感增强 / **闻灯-白底半身** / **闻灯-白底全身** / 夜市百相簿 / 沧元图片 / 沧元视频。
- `_节点截图\` 存界面与节点截图。

## 远程 ComfyUI（2026-09-16 启用）

- 地址形如 `https://gw-<hash>.cn-beijing.aigclinks.com:8016/`，前端 hash 里的 UUID 就是当前工作流 id。
- 实测环境：ComfyUI **0.30.1**，前端 1.47.12，Python 3.12.10，PyTorch **2.8.0+cu128**，
  显卡 **NVIDIA RTX5880-Ada-48Q，显存 48GB**（`--disable-cuda-malloc --disable-dynamic-vram --enable-cors-header * --listen 0.0.0.0`）。
- 可用的 checkpoint 只有 `majicmixRealistic_v7 (1).safetensors` 和 `v1-5-pruned-emaonly-fp16.safetensors`。
- API 直连可用（自签证书需 `ssl` 不校验）：`/system_stats`、`/object_info/<节点>`、`/history`、`/queue`。
  `GET /history` 能导出 submit 时的**完整 prompt dict**，是核对界面上真实参数的最可靠手段。
- ⚠️ `/api/userdata?dir=workflows` 返回 `[]` → **工作流没存到服务器**，只活在浏览器会话里。


## ★ 2026-09-18 增补两条硬规则（当天实测，代价是用户白等半小时）

1. **网关地址每次开机都变**（hash 变，旧地址对所有路径返回 400 页面）。
   已让活跃脚本支持 **COMFY_BASE 环境变量覆盖**，换网关只需带上 `COMFY_BASE=...` 或改默认值，
   不必逐个改代码。当天已全量刷新 _scripts/*.py 共 39 个文件。

2. **上行带宽只有约 40 KB/s** —— 1.71 MB 上传要 42 秒，5.42 MB 要 2 分钟以上。
   凡上传一律先缩到 1~2 MB；大图会被 timeout 判成"卡死"，实际是慢死在传输里。
   身份基图请用 _wf/flux_face_base_v23_1024x1280.png（1.71 MB），不要用 1792x2304 原图。
   验证落地用 `GET /object_info/LoadImage`（它的 image 列表就是 input/ 目录内容）；
   注意 `GET /internal/files/input` 返回的是 **"名字.png [input]" 这种字符串数组**，不是 dict，
   按纯文件名比对会把上传成功误判成失败（当天就是这样卡住推送的）。

3. 服务器上存在同名干扰项 `夜市百相簿 (Copy).json`（用户手工复制的）。
   推送只更新 `夜市百相簿.json`；要验证新版必须开这一份。


## ★★ PIL 只在系统 Python 里（2026-09-18）

- 系统 `C:\Users\Administrator\AppData\Local\Programs\Python\Python313\python.exe` → **有 PIL 12.1.0**
- 托管 `C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe` → **无 PIL**
- → 拼图 / 缩放 / 裁切（`make_sheet.py`、`zoom_sheet.py`、对比图）**一律用系统 python**；
  纯网络与 JSON 处理用哪个都行。
