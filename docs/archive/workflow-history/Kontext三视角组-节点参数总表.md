# 【闻灯】Flux 文生图 · 一体化 fp8 组 — 节点参数总表

> 来源：线上工作流「夜市百相簿-主工作流」实拉整理（2026-09-22，网关 gw-c8f4f224…:8016）。
> 分组标题：【闻灯】Flux 文生图 · 一体化 fp8（00009 → Kontext 左/右侧脸）
> 组内共 **29 个节点**：启用 24 个（mode=0），禁用 5 个（mode=2，旧右脸支路留作后路）。

## 一、这条链路在干什么（三层结构）

```
闻灯正脸成品 00009（唯一身份基准）
   │
   ├─► ① 统一正脸：Kontext 以 00009 为身份锚，纯噪声起点 d1.0 完整重绘质感
   │         │
   │         └─► ② 左侧脸：以「统一后的正脸」为身份锚，纯噪声 d1.0 转头 90°（鼻尖朝画面左）
   │                   │
   │                   └─► ③ 右侧脸：不做第二次生成，直接把左侧脸水平翻转（方向硬保证）
```

三张图同人、同质感的原理：**身份不是来自底模，而是来自参考图锚定（ReferenceLatent）**；
侧脸锚的是统一后的新正脸，所以三视角质感天然同源；右脸是像素级镜像，方向不靠赌提示词。

## 二、模型加载（3 个）

| ID | 节点 | 参数 |
|---|---|---|
| 1024 | UNETLoader | unet=`FLUX1\flux1-schnell.safetensors`（**内容是 Kontext**，借白名单槽位名），dtype=default |
| 1025 | DualCLIPLoader | clip1=`t5\t5xxl_fp8_e4m3fn_scaled.safetensors`，clip2=`clip_l.safetensors`，type=flux，device=default |
| 1026 | VAELoader | vae=`FLUX1\ae.safetensors` |

## 三、身份源链（3 个）

| ID | 节点 | 参数 / 接线 |
|---|---|---|
| 1027 | LoadImage | 图像=`wendeng_face_confirmed_00009.png`（★ 唯一身份基准，须先上传到服务器 input 目录） |
| 1028 | FluxKontextImageScale | 无参数（自动缩到 Kontext 合适尺寸，**勿手写宽高**），1027 → 1028 |
| 1029 | VAEEncode | 1028 → pixels，vae←1026；输出参考 latent → 1045（正脸身份锚） |

## 四、① 统一正脸支路（8 个）

| ID | 节点 | 参数 / 接线 |
|---|---|---|
| 1043 | CLIPTextEncode | **正脸编辑指令**（2608 字符，原文见附录 A），clip←1025 |
| 1044 | FluxGuidance | guidance=**3.0**，1043 → 1044 |
| 1045 | ReferenceLatent | conditioning←1044，**latent←1029（00009 参考图 = 身份锚）** |
| 1046 | KSampler | seed=**20260920**(fixed)，steps=**20**，cfg=**1.0**，sampler=**euler**，scheduler=**simple**，denoise=**1.0**；model←1024，positive←1045，negative←1030，**latent_image←1052（纯噪声起点）** |
| 1047 | VAEDecode | 1046 → 1047，vae←1026 |
| 1048 | SaveImage | prefix=`闻灯Kontext统一正脸-成品` |
| 1052 | EmptySD3LatentImage | **880×1184**，batch=1（正脸/左脸两条支路共用的纯噪声 latent） |

## 五、② 左侧脸支路（6 个）

| ID | 节点 | 参数 / 接线 |
|---|---|---|
| 1031 | CLIPTextEncode | **左脸转头指令**（1209 字符，原文见附录 B），clip←1025 |
| 1032 | FluxGuidance | guidance=**3.0** |
| 1033 | ReferenceLatent | conditioning←1032，**latent←1050（统一后正脸的 latent = 身份锚）** |
| 1034 | KSampler | seed=**20260920**(fixed)，steps=**20**，cfg=**1.0**，sampler=**euler**，scheduler=**simple**，denoise=**1.0**；latent_image←1052 |
| 1035 | VAEDecode | 1034 → 1035；输出 → 1036（存图）+ **1051（翻转）** |
| 1036 | SaveImage | prefix=`闻灯主图-左侧脸-成品` |

侧脸身份锚的子链：**1047（正脸图）→ 1049 FluxKontextImageScale → 1050 VAEEncode → 1033.latent**

| ID | 节点 | 参数 / 接线 |
|---|---|---|
| 1049 | FluxKontextImageScale | 无参数，1047 → 1049 |
| 1050 | VAEEncode | 1049 → pixels，vae←1026；输出 → 1033 |

## 六、③ 右侧脸（2 个，不采样）

| ID | 节点 | 参数 / 接线 |
|---|---|---|
| 1051 | ImageFlip | method=**y-axis: horizontally**（水平翻转），1035 → 1051 |
| 1042 | SaveImage | prefix=`闻灯主图-右侧脸-成品`，1051 → 1042 |

## 七、共用负向（1 个）

| ID | 节点 | 参数 |
|---|---|---|
| 1030 | CLIPTextEncode | text=**空字符串**。★ cfg=1.0 下负向通道本就不生效，留空仅为满足接口；三条 KSampler 的 negative 都接它 |

## 八、禁用的旧右脸支路（5 个，mode=2，仅留作后路，勿删勿启用）

| ID | 节点 | 参数 / 状态 |
|---|---|---|
| 1037 | CLIPTextEncode | 旧右侧脸转头指令（965 字符，附录 C），已禁用 |
| 1038 | FluxGuidance | guidance=3.0，已禁用 |
| 1039 | ReferenceLatent | **latent 输入为空**（旧锚已拆），已禁用 |
| 1040 | KSampler | seed=20260917(fixed)，steps=20，cfg=1.0，euler/simple，denoise=1.0，**latent_image 为空**，已禁用 |
| 1041 | VAEDecode | 已禁用 |

> 这条旧支路当年靠提示词赌"RIGHT"方向，实测会收敛成和左脸同向——已被 1051 ImageFlip 方案取代。

## 九、关键参数一览（记这几个数就够）

| 项 | 值 | 说明 |
|---|---|---|
| 底模 | flux1-schnell.safetensors（Kontext fp8） | 借名落盘，内容是 Kontext |
| Guidance | 3.0 | 三条支路一致 |
| seed | 20260920 fixed | 正脸/左脸相同；**改 seed = 换人，选定后勿动** |
| steps / cfg | 20 / 1.0 | Kontext 标准；cfg=1.0 ⇒ 负向无效，约束全靠正向指令写 |
| sampler / scheduler | euler / simple | |
| denoise | **1.0** | 纯噪声起点完整重绘——不用参考 latent 当起点，避免复刻原图 |
| 噪声尺寸 | 880×1184（16 通道 EmptySD3LatentImage） | 三视角共用 |
| 身份锚 | 正脸←00009 参考图；左脸←统一后正脸；右脸←左脸镜像 | 身份锁核心 |

## 附录 A：正脸编辑指令（节点 1043，第八版·当前线上）

```
Regenerate the image as a natural high-end photographic portrait while preserving the exact identity of the reference person.
The person is clearly a 24-year-old young adult East Asian man in his early twenties.
Keep the visual identity of a natural contemporary East Asian man. His overall appearance should remain naturally Asian and grounded in the reference image, without introducing strongly Western facial characteristics.
Preserve a youthful adult appearance and youthful facial proportions. He should look like a healthy 24-year-old Asian man, not a teenager and not a mature man in his thirties.
Preserve the exact facial identity and recognizable facial structure of the reference.
His skin should look like real young adult male skin, not beauty-retouched skin. Keep realistic fine skin texture, subtle visible pores, fine natural facial microtexture, soft peach fuzz, subtle natural skin variation and realistic skin reflectance. The skin surface should remain healthy and intact without exaggerated pores or roughness.
Do not smooth the skin excessively. Do not create airbrushed skin, plastic skin or beauty-filter skin.
Keep the complexion clean and healthy without acne, acne scars, pitted scars, wrinkles, age spots, melasma, hyperpigmentation, brown patches or dirty-looking discoloration.
Keep the eyebrows naturally dense but realistic, with visible individual eyebrow hairs, fine hair texture, natural hair direction and slightly irregular natural density.
Keep very short natural facial stubble. The moustache and chin stubble should consist of fine individual hairs with visible separation and visible skin between the hairs. Keep the facial hair subtle and low contrast, never a solid dark patch.
Keep the black wavy hair soft, airy and naturally voluminous. Preserve naturally separated waves, soft hair groupings and a limited number of fine flyaway hairs. Hair should have realistic soft hair texture and natural variation, not look wet, oily, glossy, stiff, gelled or glued together.
A single small dark mole is clearly visible at the outer corner of his LEFT eye. The mole is small, round and naturally embedded in the skin. It is a distinctive identity marker and must remain visible. Do not remove, blur, cover or relocate the mole.
Keep natural photographic color, soft realistic lighting, restrained contrast and realistic photographic detail. Avoid beauty retouching and excessive sharpening.
Keep the overall appearance naturally East Asian and faithful to the reference. Do not introduce strongly Western, European, Mediterranean or Middle Eastern facial characteristics.
```

## 附录 B：左侧脸转头指令（节点 1031，第四版·当前线上）

```
Turn the same person into a true 90-degree LEFT profile.
Preserve the exact same facial identity, age appearance, facial proportions, nose structure, lips, chin, jawline, cheekbone structure, hairline and mole placement.
The skin should remain clean, healthy and youthful. Keep a smooth intact skin surface with only very subtle natural photographic texture.
Keep the complexion clear and even. The face and neck must have a consistent natural skin tone.
Do not introduce acne, acne scars, pitted skin, enlarged pores, wrinkles, freckles, age spots, melasma, hyperpigmentation, brown patches, yellow patches, dirty-looking skin or large areas of uneven pigmentation.
The eyebrows remain soft and naturally sparse, with visible skin between individual hairs.
Keep only very subtle moustache and chin stubble. Facial hair is short, sparse and low contrast, never a solid dark patch.
The black wavy hair remains soft, airy and naturally separated into loose locks. Use soft hair transitions and only a few fine flyaway hairs. Hair must look dry and natural, never wet, oily, glossy, stiff or gelled.
Keep the same clean youthful photographic appearance, natural skin color, soft lighting and restrained contrast.
```

## 附录 C：旧右侧脸指令（节点 1037，已禁用，仅存档）

```
Use the uploaded reference image as the identity reference for the same person. Preserve the same recognizable person and facial identity, including: facial proportions, overall face shape, eye shape and spacing, eyebrows, nose, lips, cheekbones, jawline, chin, hairline, moles and overall age appearance. Preserve the same natural youthful complexion and skin tone, but reconstruct the skin naturally rather than copying individual skin defects or artifacts from the reference. Preserve the same general black wavy hairstyle and blue shirt. Change only the head direction and camera angle. Do not redesign, age, beautify, masculinize, feminize or replace the person's face. Create the opposite-facing profile from the left-profile version: his nose points toward the RIGHT edge of the image and the back of his head is on the LEFT. Show a true 90-degree profile with exactly one visible eye and one visible ear. His face must look to image-right, never image-left.
```
