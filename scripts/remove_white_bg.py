"""F4 工具:从图片去除白色背景,输出透明 PNG。

适用场景:ChatGPT/DALL·E 生成的 portrait 通常带白色 / 接近白色背景。
直接用阈值法会误伤角色身上的白色像素(衣服/眼白/高光)。
本脚本用 **flood-fill 从图像 4 个角往内扩散** 的方法,只把"和角落连通的"
背景像素 alpha=0,角色内部的白色像素保留。

依赖: pip install pillow numpy

用法:
  python scripts/remove_white_bg.py input.png [--threshold 240] [--output output.png]
  python scripts/remove_white_bg.py input_dir/  # 批量处理目录
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except ImportError as e:
    print(f"ERROR: 缺依赖 {e}。请运行: pip install pillow numpy", file=sys.stderr)
    sys.exit(1)


def remove_white_background(
    input_path: Path,
    output_path: Path,
    threshold: int = 240,
    feather: int = 1,
) -> tuple[int, int]:
    """从图像移除白色背景。

    Args:
        input_path: 输入图片(任意 PIL 支持的格式)
        output_path: 输出 PNG(强制 PNG 才能保 alpha)
        threshold: 像素 RGB 任一通道 ≥ 此值视为"接近白色背景候选"(0-255)
                   240 = 比较严格 / 220 = 比较宽松(连浅黄都会被去)
        feather: 边缘羽化(像素)— alpha 渐变,让抠图边缘不生硬

    Returns:
        (transparent_pixels, total_pixels)
    """
    img = Image.open(input_path).convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3]

    # 步骤 1:生成"接近白色"mask
    white_mask = np.all(rgb >= threshold, axis=2)

    # 步骤 2:flood-fill 从 4 个角往内 — 只有和角落连通的白色才算背景
    # 用 BFS / 简化为 scipy.ndimage.label
    try:
        from scipy.ndimage import label
        labels, num = label(white_mask)
        # 找 4 个角的 label id
        corner_labels = set()
        for cy, cx in [(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)]:
            if white_mask[cy, cx]:
                corner_labels.add(labels[cy, cx])
        # 只有这些连通分量算背景
        bg_mask = np.isin(labels, list(corner_labels))
    except ImportError:
        # 没有 scipy → 用 BFS 自己实现
        bg_mask = np.zeros((h, w), dtype=bool)
        from collections import deque
        queue: deque = deque()
        for cy, cx in [(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)]:
            if white_mask[cy, cx] and not bg_mask[cy, cx]:
                queue.append((cy, cx))
                bg_mask[cy, cx] = True
        while queue:
            y, x = queue.popleft()
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and white_mask[ny, nx] and not bg_mask[ny, nx]:
                    bg_mask[ny, nx] = True
                    queue.append((ny, nx))

    # 步骤 3:把 bg_mask 像素的 alpha 设 0
    new_alpha = arr[:, :, 3].copy()
    new_alpha[bg_mask] = 0

    # 步骤 4:**边缘 anti-alias 处理** — bg 边界外 ring 内,接近白的像素按 luminance fade
    # 这能干净抠掉 AI 生成图边缘的渐变白边,且不误伤角色身上的纯白(因为不在 ring 内)
    if feather > 0:
        try:
            from scipy.ndimage import distance_transform_edt
            fg_mask = ~bg_mask
            # 每个 fg 像素到最近 bg 像素的距离
            dist = distance_transform_edt(fg_mask)
            # ring = 距离 1..feather*2 的边界带(放宽 ring 宽度抓更多 anti-alias)
            ring_width = max(feather * 3, 4)
            ring_mask = (dist > 0) & (dist <= ring_width)
            # 计算 luminance(0-255)
            luminance = (rgb[:, :, 0].astype(np.float32) + rgb[:, :, 1].astype(np.float32) + rgb[:, :, 2].astype(np.float32)) / 3.0
            # luminance > LUM_HI(纯白)→ alpha=0;luminance < LUM_LO(正常)→ alpha 不变;中间 linear
            LUM_HI = 250.0  # 纯白
            LUM_LO = 200.0  # 正常色阈值
            # fade_factor: 1.0 = 完全保留 alpha,0.0 = 完全透明
            fade_factor = np.clip((LUM_HI - luminance) / (LUM_HI - LUM_LO), 0.0, 1.0)
            # 只在 ring_mask 内应用 fade
            ring_alpha = (new_alpha.astype(np.float32) * fade_factor).astype(np.uint8)
            new_alpha = np.where(ring_mask, ring_alpha, new_alpha)
        except ImportError:
            pass  # 没有 scipy 跳过

    arr[:, :, 3] = new_alpha
    out_img = Image.fromarray(arr, "RGBA")
    out_img.save(output_path, "PNG")

    transparent = int(bg_mask.sum())
    total = h * w
    return transparent, total


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input", help="输入图片或目录")
    p.add_argument("--output", "-o", help="输出文件(单文件模式)。默认覆盖输入或加 _nobg")
    p.add_argument("--threshold", "-t", type=int, default=240, help="白色阈值 0-255,默认 240")
    p.add_argument("--feather", "-f", type=int, default=1, help="边缘羽化像素,默认 1")
    p.add_argument("--suffix", default="_nobg", help="批量模式输出后缀,默认 _nobg")
    args = p.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: {input_path} 不存在", file=sys.stderr)
        sys.exit(1)

    if input_path.is_dir():
        # 批量
        count = 0
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            for fp in input_path.glob(f"*{ext}"):
                if args.suffix in fp.stem:
                    continue  # 跳过自己之前输出的
                out = fp.with_name(fp.stem + args.suffix + ".png")
                t, total = remove_white_background(fp, out, args.threshold, args.feather)
                pct = 100.0 * t / total
                print(f"  {fp.name} → {out.name}  抠掉 {t}/{total} ({pct:.1f}%) 像素")
                count += 1
        print(f"\n批量完成,处理 {count} 张图片")
    else:
        out = Path(args.output) if args.output else input_path.with_name(input_path.stem + "_nobg.png")
        t, total = remove_white_background(input_path, out, args.threshold, args.feather)
        pct = 100.0 * t / total
        print(f"{input_path} → {out}")
        print(f"抠掉 {t}/{total} ({pct:.1f}%) 像素")


if __name__ == "__main__":
    main()
