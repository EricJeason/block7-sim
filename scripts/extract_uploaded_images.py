"""F4 工具脚本:从 Claude Code session jsonl 提取用户上传的 base64 图片到磁盘。

背景:Eric 用平板远程操控 Claude Code 时,无法直接把图片放到电脑文件系统。
他通过对话上传的图片会被 Claude Code 自动存进 session jsonl(base64 编码)。
本脚本扫描 jsonl,把每个 image 提取出来按时间序保存到 docs/uploaded/。

用法:
  python scripts/extract_uploaded_images.py [output_dir]
默认 output_dir = docs/uploaded/

每个图片命名: img_<n>_<line>_<media_type>.png/jpg
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path

# Windows console 默认 GBK,中文输出会乱码 — 强制 UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 自动找当前 worktree 的 session jsonl
SCRIPT_DIR = Path(__file__).resolve().parent
WORKTREE_ROOT = SCRIPT_DIR.parent
# Claude Code 目录名转换规则:`:` `\` `/` `.` 都替换为 `-`
# 例:`C:\Users\...\block7-sim\.claude\worktrees\blissful-knuth-4716c6`
#  → `C--Users-...-block7-sim--claude-worktrees-blissful-knuth-4716c6`
worktree_str = str(WORKTREE_ROOT)
key = worktree_str
for ch in (":", "\\", "/", "."):
    key = key.replace(ch, "-")
home = Path.home()
projects_dir = home / ".claude" / "projects" / key

if not projects_dir.exists():
    # 尝试 fallback: 找最近修改的 dir
    parent = home / ".claude" / "projects"
    if parent.exists():
        candidates = sorted(parent.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            projects_dir = candidates[0]
            print(f"WARN: 推断 projects 目录 = {projects_dir.name}", file=sys.stderr)

if not projects_dir.exists():
    print(f"ERROR: 找不到 session 目录 {projects_dir}", file=sys.stderr)
    sys.exit(1)

# 找最新的 .jsonl(最近 session)
jsonl_files = sorted(projects_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
if not jsonl_files:
    print(f"ERROR: {projects_dir} 下没有 .jsonl 文件", file=sys.stderr)
    sys.exit(1)

session_file = jsonl_files[0]
print(f"扫描 session: {session_file.name}  ({session_file.stat().st_size // 1024} KB)")

# 默认输出目录
output_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else WORKTREE_ROOT / "docs" / "uploaded"
output_dir.mkdir(parents=True, exist_ok=True)


def walk_for_images(node, out_list, line_no):
    """递归找 content type=image source.type=base64。"""
    if isinstance(node, dict):
        if node.get("type") == "image" and isinstance(node.get("source"), dict):
            src = node["source"]
            if src.get("type") == "base64":
                out_list.append({
                    "line": line_no,
                    "media_type": src.get("media_type", "image/png"),
                    "data": src.get("data", ""),
                })
        for v in node.values():
            walk_for_images(v, out_list, line_no)
    elif isinstance(node, list):
        for v in node:
            walk_for_images(v, out_list, line_no)


images = []
with session_file.open("r", encoding="utf-8") as f:
    for line_no, line in enumerate(f, 1):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        walk_for_images(obj, images, line_no)

print(f"\n找到 {len(images)} 张 base64 图片")

# 去重 — 用 sha256 完整哈希,不同图片绝不冲突
seen_hashes = set()
saved_count = 0
for idx, img in enumerate(images):
    data_str = img["data"]
    fingerprint = hashlib.sha256(data_str.encode("ascii")).hexdigest()
    if fingerprint in seen_hashes:
        continue
    seen_hashes.add(fingerprint)

    media_type = img["media_type"]
    ext_map = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/gif": "gif",
    }
    ext = ext_map.get(media_type, "bin")

    out_name = f"img_{saved_count:03d}_line{img['line']:05d}.{ext}"
    out_path = output_dir / out_name
    try:
        raw = base64.b64decode(data_str)
    except Exception as e:
        print(f"  跳过 line {img['line']}:base64 decode 失败 ({e})", file=sys.stderr)
        continue

    out_path.write_bytes(raw)
    saved_count += 1
    print(f"  → {out_name}  ({media_type}, {len(raw)} bytes)")

print(f"\n保存 {saved_count} 张图片到 {output_dir}")
