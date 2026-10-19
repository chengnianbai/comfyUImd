# -*- coding: utf-8 -*-
"""等 Kontext 落盘 → 日志权威判据 → 最小链路验货。只读，不提交任何下载。"""
import sys, time

sys.path.insert(0, ".")
import fix_kontext_model as fk

print("=" * 72)
print("等 Kontext 落盘（约 11:54 前后）+ 验货")
print("=" * 72)

t0 = time.time()
done = fk.wait_queue(20)          # 最多等 20 分钟
print("\n队列结束标记 = %s   已等 %.0f 秒" % (done, time.time() - t0))
fk.tail_log()

unets = fk.combo("UNETLoader", "unet_name")
unet = [x for x in unets if "schnell" in x][0]
vaes = fk.combo("VAELoader", "vae_name")
vae = [x for x in vaes if "ae.safetensors" in x][0]
print("\n[验货] UNET=%r  VAE=%r" % (unet, vae))
ok, why = fk.probe_unet(unet, vae)
print("   %s %s" % ("✔" if ok else "✘", why))
print("\n结论：%s" % ("Kontext 可用，转头组可跑" if ok else "仍不可用，看上面日志"))
