# ============================================================
#  闻灯角色出图 - 云端 ComfyUI 模型下载脚本
#  平台：Windows（PowerShell 5.1 可用）
#  用法：把下面 $COMFY 改成云端那台机器的 ComfyUI 根目录，然后在 PowerShell 里运行
#        powershell -ExecutionPolicy Bypass -File download_models_cloud.ps1
#
#  全部地址已于 2026-09-16 实测可下载（HTTP 200）
#
#  重要前提：那台云端机器没有装 ComfyUI-Impact-Pack，
#  所以 FaceDetailer 相关目录（ultralytics/sams）和节点都不存在。
#  本脚本默认只下「放大模型 + 底模」，这两项用核心节点就能跑。
#  脸部精修（face_yolov8m / mobile_sam）默认注释掉，等装好插件再开。
# ============================================================

$COMFY = "D:\ComfyUI"          # <<< 改成你的 ComfyUI 根目录

# ---------- 建目录 ----------
# 这三个都是 ComfyUI 核心自带或必有的目录，创建是安全的
$dirs = @(
  "$COMFY\models\checkpoints",
  "$COMFY\models\upscale_models"
)
foreach ($d in $dirs) {
  if (!(Test-Path $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null; Write-Host "created $d" }
}

# ---------- 下载清单 ----------
$files = @(

  # ===== 第 1 批：放大链路（必下，共 134 MB）=====
  # 目标目录 models/upscale_models/ 已存在，用核心节点 UpscaleModelLoader 即可加载

  @{ Name = "4x-UltraSharp.pth (ESRGAN 放大，偏锐)"
     Url  = "https://hf-mirror.com/Kim2091/UltraSharp/resolve/main/4x-UltraSharp.pth"
     Dst  = "$COMFY\models\upscale_models\4x-UltraSharp.pth" },

  @{ Name = "4x_NMKD-Superscale (放大，偏自然)"
     Url  = "https://hf-mirror.com/uwg/upscaler/resolve/main/ESRGAN/4x_NMKD-Superscale-SP_178000_G.pth"
     Dst  = "$COMFY\models\upscale_models\4x_NMKD-Superscale-SP_178000_G.pth" },

  # ===== 第 2 批：首选 SDXL 底模（6.9 GB）=====
  # 亚洲人像，训练集含男性与全身照。装上后 CFG 要改 10、Clip Skip 要改 1

  @{ Name = "HelloWorld XL 7.0 (首选底模)"
     Url  = "https://www.modelscope.cn/models/Leosam1/LEOSAM_s_HelloWorld_XL_HelloWorld_XL_7.0/resolve/master/leosamsHelloworldXL_helloworldXL70.safetensors"
     Dst  = "$COMFY\models\checkpoints\leosamsHelloworldXL_helloworldXL70.safetensors" }

  # ===== 备选底模：皮肤质感最强，不需要就整段注释掉 =====
  # ,@{ Name = "RealVisXL V5.0 (备选底模)"
  #    Url  = "https://hf-mirror.com/SG161222/RealVisXL_V5.0/resolve/main/RealVisXL_V5.0_fp16.safetensors"
  #    Dst  = "$COMFY\models\checkpoints\RealVisXL_V5.0_fp16.safetensors" }

  # ===== 第 3 批：脸部精修 —— 需要先装 Impact Pack，装好后取消注释 =====
  # 装插件（在 ComfyUI 根目录执行）：
  #   cd custom_nodes
  #   git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack.git
  #   （GitHub 不通就用 https://gh-proxy.com/https://github.com/... ）
  # 重启 ComfyUI 后，models/ultralytics/bbox 和 models/sams 会自动创建
  #
  # ,@{ Name = "face_yolov8m.pt (脸部检测)"
  #    Url  = "https://hf-mirror.com/Bingsu/adetailer/resolve/main/face_yolov8m.pt"
  #    Dst  = "$COMFY\models\ultralytics\bbox\face_yolov8m.pt" }
  #
  # ,@{ Name = "mobile_sam.pt (分割)"
  #    Url  = "https://hf-mirror.com/dhkim2810/MobileSAM/resolve/main/mobile_sam.pt"
  #    Dst  = "$COMFY\models\sams\mobile_sam.pt" }
)

# ---------- 执行 ----------
foreach ($f in $files) {
  Write-Host ""
  Write-Host ("==> " + $f.Name)
  if (Test-Path $f.Dst) {
    $sz = [math]::Round((Get-Item $f.Dst).Length / 1MB, 1)
    Write-Host ("    已存在 (" + $sz + " MB)，跳过。要重下请先删除该文件。")
    continue
  }
  # -L 跟随重定向  -C - 断点续传  --retry 3 失败重试
  curl.exe -L -C - --retry 3 --fail -o $f.Dst $f.Url
  if ($LASTEXITCODE -eq 0) {
    $sz = [math]::Round((Get-Item $f.Dst).Length / 1MB, 1)
    Write-Host ("    OK  " + $sz + " MB")
  } else {
    Write-Host ("    失败 (curl exit " + $LASTEXITCODE + ")")
  }
}

Write-Host ""
Write-Host "完成。回到 ComfyUI 界面点右上角 Refresh 刷新模型列表。"
