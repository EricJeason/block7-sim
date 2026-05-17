# 11 个 NPC portrait ChatGPT 生成提示词

> **目标**:256×256 像素 anime-pixel bust shot(胸像),透明或纯色背景,用于 F4.4 DialogueSession modal + 后续 C 角色面板 / P 图鉴。
> **来源**:`backend/data/personas/agent_XX.yaml` 的 `appearance` 字段。
> **风格统一**:Granblue Fantasy x Stardew Valley anime-pixel,暮谷镇暮黄/苔绿/旧橡木墨调色,悬疑生活流氛围。

---

## 通用 prompt prefix(每张都加在前面)

**中文**:
> Anime 像素艺术胸像,256×256,Granblue Fantasy 像素版 + Stardew Valley 调色,
> 暮黄 / 苔绿 / 旧橡木墨 muted 色调,柔和暖光,**透明背景**(transparent PNG)。
> 氛围:悬疑生活流 + 循环 horror,人物表情下藏着秘密但不张扬。
> 不要边框,不要文字,不要 logo。

**英文**(给 ChatGPT/DALL·E 用):
> Anime-pixel art bust portrait, 256x256 pixels, in the style of Granblue Fantasy
> pixel art and Stardew Valley palette. Muted ochre/sage/oak-ink tones, soft warm
> lighting. Quiet unease mood (horror/slice-of-life game). **Transparent background
> (PNG)**. No border, no text, no logo.

---

## 1. 林秋(agent_01)村医 · 32 岁女 · **治愈者**

**核心特征**:黑色长直发松束脑后 / 浅蓝工作服 + 围裙 / 袖口药渍 / 眼神专注 / 修长手指有薄茧

**英文 prompt**(直接复制):
```
[通用 prefix] +
Lin Qiu, 32-year-old Chinese village herbalist doctor. Black straight long hair
loosely tied behind her head. Wearing pale blue work robe with apron, herb-stained
sleeve cuffs. Slender fingers with thin calluses. Focused, gentle gaze. Holding a
small mortar or herb bundle. Hidden weariness in her eyes. Off-white parchment
background. Anime-pixel bust shot.
```

---

## 2. 阿杏(agent_02)解药学徒 · 24 岁女 · **治愈者**

**核心特征**:圆脸 / 齐肩短发用发带束 / 大眼睛带黑眼圈 / 浅黄短袍工作服 / **手腕内侧 3 道淡痕**(感染印记)

**英文 prompt**:
```
[通用 prefix] +
A-xing, 24-year-old young Chinese herbalist apprentice. Round face, shoulder-length
black hair held by a simple hairband. Bright big eyes but with faint dark circles.
Wearing pale yellow short work robe. Cheerful but slightly anxious expression.
Lighting hint: three pale crescent marks on her inner wrist faintly glowing.
Off-white parchment background. Anime-pixel bust shot.
```

---

## 3. 早纪(agent_03)协会驻村员 · 28 岁女

**核心特征**:日本血统 / 略苍白皮肤 / 黑色长发用簪子盘起 / 半框眼镜 / 深蓝长袍裙 + 协会徽章 / 手持皮质笔记本

**英文 prompt**:
```
[通用 prefix] +
Saki, 28-year-old Japanese-blooded researcher (Pioneer Society liaison). Slightly
pale skin (from long nights). Long black hair pinned up with a kanzashi.
Half-frame glasses. Wearing a simplified dark blue Society robe-dress with a small
emblem on the left chest. Holding a leather-bound notebook. Composed, observant
expression. Off-white parchment background. Anime-pixel bust shot.
```

---

## 5. 沈砚(agent_05)村长 · 55 岁男

**核心特征**:中等偏瘦 / 鬓角花白 / 深灰长褂 / **腰挂一串旧钥匙**(几把已无对应锁) / 关节粗大但稳定 / 疲惫又锐利的眼神

**英文 prompt**:
```
[通用 prefix] +
Shen Yan, 55-year-old Chinese village chief. Lean build, graying temples.
Wearing a dark gray long robe. A bundle of old keys hangs at his waist (some keys
no longer have locks). Large but steady knuckles. Tired yet sharp gaze, carries
thirty years of secrets. Slight stoop. Off-white parchment background. Anime-pixel
bust shot.
```

---

## 6. 千绫(agent_06)捕魔队长 · 35 岁女

**核心特征**:东亚血统 / 黑发短马尾 / 深蓝作战服 + 皮护肩 / **腰挂短刀 + 捕魔符** / 左眼角隐约疤 / 锐利眼神(看林秋时会软下来)

**英文 prompt**:
```
[通用 prefix] +
Qian Ling, 35-year-old East Asian female monster-hunting captain (retired military).
Black hair in a short ponytail, disciplined posture. Wearing dark navy combat
uniform with leather shoulder guard. A short sword and a few demon-warding talismans
at her belt. A subtle scar near her left eye. Sharp, intense gaze with a hidden
softness. Off-white parchment background. Anime-pixel bust shot.
```

---

## 7. 苏拂(agent_07)酒馆主 · 40 岁女

**核心特征**:中等身材偏丰腴 / 栗色长发松挽 + **银簪** / 深红或暗紫长袍 / 袖口卷到肘 / 圆亮眼睛 / 笑容有感染力 / 双手粗糙但快

**英文 prompt**:
```
[通用 prefix] +
Su Fu, 40-year-old Chinese tavern owner. Plump middle-aged woman with chestnut
brown long hair loosely tied with a silver hairpin. Wearing a deep crimson or
dark purple long robe with sleeves rolled to elbows. Round bright eyes, warm
infectious smile. Hands rough but quick. Holding a wine cup or wiping a glass.
Off-white parchment background. Anime-pixel bust shot.
```

---

## 8. 马九(agent_08)跑商 · 38 岁男

**核心特征**:风吹日晒偏黑糙肤 / 鬓角灰 / 深褐长袍 + 皮腰带 + 小皮囊 / 没刮干净的胡茬 / 细长灵活的眼睛

**英文 prompt**:
```
[通用 prefix] +
Ma Jiu, 38-year-old Chinese traveling merchant. Sun-weathered tan skin, slight
gray at temples. Stubbled chin. Wearing a sturdy dark brown long robe with leather
belt. A small worn leather pouch hangs at his belt. Narrow, lively, calculating
eyes. Slight roguish smile. Off-white parchment background. Anime-pixel bust shot.
```

---

## 9. 田柱(agent_09)铁匠 · 50 岁男

**核心特征**:结实体格 / **双臂打铁烫疤** / 剃光头 + 浓密黑胡子 / 深棕厚围裙 / 颈挂粗皮绳护身符(亡妻遗物) / 指甲缝永远是炭灰

**英文 prompt**:
```
[通用 prefix] +
Tian Zhu, 50-year-old Chinese blacksmith. Burly muscular build, both arms scarred
from years of forging. Shaved head with thick black beard. Wearing a heavy dark
brown leather apron. A small amulet on a thick leather cord around his neck (his
late wife's keepsake). Soot-stained fingernails. Gruff but kind expression.
Off-white parchment background. Anime-pixel bust shot.
```

---

## 10. 文姐(agent_10)农场主 · 45 岁女 · 林秋闺蜜

**核心特征**:南方湿热血统 / 麦色圆脸 / 黑长发用深绿头巾包 / 深绿短袍 + 工作裤 / 手指带泥但干净 / **颈挂磨滑的小石头吊坠**(亡子玩具)

**英文 prompt**:
```
[通用 prefix] +
Wen Jie, 45-year-old Chinese herb farm owner from southern humid regions. Wheat-
toned round face, gentle but worn. Long black hair wrapped in a dark green
headscarf. Wearing a dark green short tunic with work trousers. Earth-stained but
clean fingers. A small smooth stone pendant on a leather cord around her neck
(her late child's keepsake). Quiet, weighty gaze. Off-white parchment background.
Anime-pixel bust shot.
```

---

## 11. 小璎(agent_11)捕魔队新人 · 19 岁女

**核心特征**:圆脸 / 圆亮双眸带活气 / **齐整黑短发用红色细绳扎小马尾** / 浅蓝作战服 + 皮护腕 / **脸颊小雀斑**

**英文 prompt**:
```
[通用 prefix] +
Xiao Ying, 19-year-old Chinese young female monster-hunter rookie. Round face,
bright round lively eyes, freckles on cheeks. Neatly cut short black hair with
a small ponytail tied by a red string. Wearing a light blue combat uniform with
leather wrist guards. Eager, slightly nervous expression. Off-white parchment
background. Anime-pixel bust shot.
```

---

## 12. 白嬤(agent_12)村中老人 · 73 岁女 · **疑似治愈者**

**核心特征**:**满头银白长发常不束** / 多皱皮肤但**清澈眼睛** / 深色粗布长袍 / **磨亮木杖** / **肩袍上有羽毛痕**(常有鸟停)

**英文 prompt**:
```
[通用 prefix] +
Bai Mo, 73-year-old elderly Chinese woman of mysterious origin. Long silver-white
hair often unbound and flowing. Wrinkled skin but strikingly clear eyes (almost
otherworldly). Wearing a dark coarse cloth long robe. Holds a worn wooden staff.
A few small feather traces on her shoulder (birds often perch on her). Serene,
timeless expression. Off-white parchment background. Anime-pixel bust shot.
```

---

## 使用建议

1. **批量生成**:可以一次给 ChatGPT 多个 prompt(每张分开生成,免得 AI 把多角色混进一张)
2. **风格一致性**:**第一张**(比如林秋)定调,后面 10 张说"和林秋的画风一致" + 具体角色描述
3. **筛选**:每个 NPC 生成 3-5 张,挑最像 persona 的那张
4. **上传给我**:平板对话直接发图(可批量),发完跟我说"图发完了 + 是 X 角色",我跑提取脚本 + 抠白边 + 放到正确目录

## 抠白边

ChatGPT/DALL·E 通常生成图带白边(不是真透明背景)。我已写 `scripts/remove_white_bg.py`,会自动:
- 检测 4 角是否纯白 / 接近白
- flood-fill 从边缘往内扩散把背景 alpha=0(不会误伤角色身上的白色像素)
- 保存为透明 PNG

你只需要发图 → 我跑脚本 → 抠完。
