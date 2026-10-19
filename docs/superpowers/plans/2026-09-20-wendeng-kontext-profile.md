# 闻灯 Kontext 左右侧脸 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户确认的 `闻灯-脸部正面-成品_00009_.png` 设为唯一参考图，部署主工作流并生成闻灯左右 90 度侧脸。

**Architecture:** 复用主工作流已有但静音的 Kontext 转头链路。用独立补丁脚本对现有 UI 工作流做最小原地修改，结构测试负责锁定参考图、节点启用状态、输出名称和依赖闭包；部署脚本负责备份远端、上传基图、推送并读回核验。

**Tech Stack:** Python 3.13、ComfyUI UI/API JSON、标准库 `json` / `urllib`、PowerShell。

## Global Constraints

- 唯一身份基准为 `闻灯-脸部正面-成品_00009_.png`。
- 左右侧脸使用服务器已有 Kontext fp8 模型和 `ReferenceLatent`。
- Guidance `3.0`；`euler + simple`；20 步；CFG `1.0`；denoise `1.0`。
- 部署前保存远端工作流快照，不删除本地产物。
- 仅运行左、右 90 度分支，不运行左 45 度或普通 FLUX img2img 身份锁分支。

---

### Task 1: 工作流补丁与结构回归测试

**Files:**
- Create: `_scripts/patch_wendeng_profiles.py`
- Create: `_scripts/test_patch_wendeng_profiles.py`
- Modify: `_scripts/_wf/夜市百相簿_主工作流.json`

**Interfaces:**
- Consumes: `patch_workflow(workflow: dict) -> dict` 接收 ComfyUI UI 工作流。
- Produces: 更新后的节点 `1024-1042`，参考图名 `wendeng_face_confirmed_00009.png`，输出前缀 `闻灯主图-左侧脸-成品` / `闻灯主图-右侧脸-成品`。

- [ ] **Step 1: 写失败测试**

测试断言节点 `1027` 指向新基图；`1024-1042` 所需节点启用；`1043-1048` 左 45 度分支保持静音；两个 SaveImage 使用新前缀；依赖闭包均包含 `LoadImage -> FluxKontextImageScale -> VAEEncode -> ReferenceLatent -> KSampler -> VAEDecode -> SaveImage`。

- [ ] **Step 2: 运行测试并确认因补丁函数不存在而失败**

Run: `python _scripts/test_patch_wendeng_profiles.py`
Expected: FAIL，无法导入 `patch_wendeng_profiles`。

- [ ] **Step 3: 实现最小补丁脚本**

脚本读取本地或指定输入 JSON，只修改节点 `1024-1048` 的 mode、标题、图片名、提示词和输出前缀，并执行内置结构校验后写回。

- [ ] **Step 4: 运行测试并验证通过**

Run: `python _scripts/test_patch_wendeng_profiles.py`
Expected: PASS。

### Task 2: 远端备份、上传与部署

**Files:**
- Create: `_scripts/deploy_wendeng_profiles.py`
- Create: `_scripts/test_deploy_wendeng_profiles.py`
- Create at runtime: `_scripts/_wf/_backup_wendeng_profiles_<timestamp>.json`

**Interfaces:**
- Consumes: 本地基准图、工作流名 `夜市百相簿-主工作流.json`、补丁后的 JSON。
- Produces: 远端 input 文件 `wendeng_face_confirmed_00009.png` 和更新后的远端工作流。

- [ ] **Step 1: 写失败测试**

测试 multipart 上传体、工作流 URL 编码、远端读回校验函数，使用内存样例而非真实服务器写操作。

- [ ] **Step 2: 运行测试并确认失败**

Run: `python _scripts/test_deploy_wendeng_profiles.py`
Expected: FAIL，部署模块尚不存在。

- [ ] **Step 3: 实现部署脚本**

先 GET 远端工作流并保存时间戳备份，再 POST `/upload/image`，随后 PUT 工作流用户数据接口，最后 GET 读回并调用 Task 1 的结构校验。

- [ ] **Step 4: 运行测试并验证通过**

Run: `python _scripts/test_deploy_wendeng_profiles.py`
Expected: PASS。

### Task 3: 部署和左右侧脸生成

**Files:**
- Modify remotely: `workflows/夜市百相簿-主工作流.json`
- Create outputs: `系列-夜市百相簿/02-角色/闻灯/设定图/主图左右侧脸/*.png`

**Interfaces:**
- Consumes: `COMFY_BASE=https://gw-efb56d453d484597a1b8ddfc86156262.cn-beijing.aigclinks.com:8016`。
- Produces: 左右侧脸成品 PNG 和远端执行记录。

- [ ] **Step 1: 运行本地完整验证**

Run: `python _scripts/test_patch_wendeng_profiles.py && python _scripts/test_deploy_wendeng_profiles.py && python _scripts/verify_master.py`
Expected: 全部退出码为 0。

- [ ] **Step 2: 执行部署并读回核验**

Run: `python _scripts/deploy_wendeng_profiles.py`
Expected: 备份、上传、推送、读回四步均成功。

- [ ] **Step 3: 分别提交左右侧脸**

Run: `python _scripts/run_wf.py "夜市百相簿-主工作流.json" "闻灯主图-左侧脸,闻灯主图-右侧脸" final "系列-夜市百相簿/02-角色/闻灯/设定图/主图左右侧脸"`
Expected: 两个 SaveImage 命中，`node_errors` 为空，任务完成并下载两张 PNG。

- [ ] **Step 4: 最终验证**

检查 PNG 可解码、尺寸非零，目视确认左右方向，并与 `00009` 并排检查发型、脸型、眉眼、鼻唇、痣与胡须等身份特征。

## Repository Note

当前工作目录不是 Git 仓库，因此计划中的阶段性 Git commit 不可执行；以带时间戳的远端工作流备份和本地文件变更作为回退依据。
