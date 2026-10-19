# -*- coding: utf-8 -*-
"""闻灯出图 —— 共用提示词文本块（Flux 版，自然语言）

为什么单独抽一个模块：
    Face / Turn 两个工作流共用同一套人物描述。以前散在两个脚本里，
    改一个「头发质感」要改两处，已经出现过改漏 → 抽成单一来源。

★ 全部为**正向自然语言**。FLUX 在 cfg=1.0 下没有 negative 分支，
  「不要 X」只能写成 "no X / not a X" 这类否定式正向短语。
"""

CHAR = ("a 24-year-old East Asian man with a masculine face, a strong angular jaw, thick dark "
        "eyebrows, deep-set dark eyes with faint shadows underneath, light stubble, and a single "
        "small beauty mark at the outer corner of one eye")

HAIR = ("His hair is messy wavy black hair, unkempt and slightly damp, with dry individual strands "
        "lifting away and separating, and a few loose strands falling across the forehead. "
        "It is completely unstyled and there is no hair product, no gel, no salon styling.")

SKIN = ("This is a raw unretouched documentary photograph. Real human skin with clearly visible "
        "pores and fine peach fuzz, subtle unevenness in skin tone, faint freckles and a scattering "
        "of small moles across the cheeks, natural creases under the eyes. "
        "No beauty retouching, no airbrushing, no skin smoothing, not a glamour shot, not a "
        "dermatology advertisement.")

LIGHT = ("Studio lighting that is soft and even overall but keeps a gentle directional key from "
         "one side, so the face still has modeling and depth instead of completely flat light.")

BGD = "Plain pure white seamless background, no props, no other people, no scenery, no furniture."

QUAL = "Sharp focus, shot on an 85mm lens at f/4, photorealistic, high detail."

WEAR = "He wears a faded blue collared shirt with a dark worn coat collar."


# ---------------- 视角 ----------------

VIEW_FRONT = ("He faces the camera directly, head level, shoulders square, face centered and "
              "looking straight into the lens, calm neutral expression.")

VIEW_34_L = ("His head is turned roughly 45 degrees to his left, a three-quarter view. The camera "
             "sees the left side of his face much more than the right: his left eye sits near the "
             "middle of the frame, the right eye is pushed out toward the far contour of his cheek, "
             "the nose is foreshortened with the far nostril wing hidden, and the far cheekbone and "
             "far jawline still just show along the edge of his face.")

VIEW_34_R = ("His head is turned roughly 45 degrees to his right, a three-quarter view. The camera "
             "sees the right side of his face much more than the left: his right eye sits near the "
             "middle of the frame, the left eye is pushed out toward the far contour of his cheek, "
             "the nose is foreshortened with the far nostril wing hidden, and the far cheekbone and "
             "far jawline still just show along the edge of his face.")

VIEW_90_L = ("A true full 90 degree side profile — his head is turned all the way so the camera "
             "sees his LEFT side only. In the frame there is exactly one eye, the left eyebrow, the "
             "left ear, the straight ridge of his nose, his lips in profile, and the line of his "
             "chin and jaw. His right eye, right eyebrow and the right half of his face are "
             "completely hidden behind the contour of his head.")

VIEW_90_R = ("A true full 90 degree side profile — his head is turned all the way so the camera "
             "sees his RIGHT side only. In the frame there is exactly one eye, the right eyebrow, "
             "the right ear, the straight ridge of his nose, his lips in profile, and the line of "
             "his chin and jaw. His left eye, left eyebrow and the left half of his face are "
             "completely hidden behind the contour of his head.")

KEEP_ID_REL = ("Keep exactly the same person, the same face, the same hair, the same lighting and "
               "the same pure white background as the input photograph — only the direction his "
               "head is turned changes.")


def compose(view, keep_id=False):
    """拼出完整正向提示词。keep_id=True 时在末尾补一段「只转头、别换人」。"""
    p = ("Photorealistic studio headshot of %s. %s %s %s %s %s %s %s"
         % (CHAR, view, WEAR, HAIR, SKIN, LIGHT, BGD, QUAL))
    if keep_id:
        p += " " + KEEP_ID_REL
    return p
