extends Node2D

## F0 视觉地基检查 — chrome StyleBox + 三组字体 + KeyCap 控件的最小可视化 demo。
##
## 用法:在 Godot 编辑器里打开 res://scenes/ui/F0_ChromeTest.tscn 然后 F6 单独运行。
## 看到:
##   - 顶部木板时钟样式("☀ DAY 3 · 15:52")
##   - 中央羊皮纸面板含三组字体中英混排(serif / handwriting / mono)
##   - 一行 KeyCap (WASD · E · Esc · Tab · 1 2 3 4)
##   - 浮空 parchment 模拟 hover whisper
##   - 封蜡红圆点 + ink rule 分隔线
##
## **F1 阶段会被删除**,只在 F0 检查点期间存在。

const KeyCapScene := preload("res://scenes/ui/KeyCap.tscn")


func _ready() -> void:
	# 全屏暗咖底(与设计稿 main-screen 背景 #1A140C 一致)
	var bg := ColorRect.new()
	bg.color = Color("#1A140C")
	bg.anchor_right = 1.0
	bg.anchor_bottom = 1.0
	add_child(bg)

	# ---------------------------- 顶部:木板时钟 ----------------------------
	var clock_panel := PanelContainer.new()
	clock_panel.add_theme_stylebox_override("panel", ChromeTheme.make_wood_plank())
	clock_panel.custom_minimum_size = Vector2(240, 52)
	clock_panel.position = Vector2(520, -4)
	add_child(clock_panel)

	var clock_label := Label.new()
	clock_label.text = "☀ DAY 3 · 15:52"
	clock_label.add_theme_font_override("font", ChromeTheme.font_serif(600))
	clock_label.add_theme_font_size_override("font_size", 21)
	clock_label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	clock_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	clock_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	clock_panel.add_child(clock_label)

	# ---------------------------- 中央:羊皮纸面板 + 三组字体 ----------------------------
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", ChromeTheme.make_parchment())
	panel.position = Vector2(240, 120)
	panel.custom_minimum_size = Vector2(800, 320)
	add_child(panel)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 14)
	panel.add_child(vbox)

	# Serif row (Cormorant + Noto Serif SC)
	var serif_row := _make_font_demo_row(
		"Serif",
		"Cormorant Garamond · Noto Serif SC · 暮谷镇 · 林秋 · 千绫 · Block-7 Sim",
		ChromeTheme.font_serif(500),
		22
	)
	vbox.add_child(serif_row)

	_add_ink_rule(vbox)

	# Handwriting row (Caveat + Ma Shan Zheng)
	var hw_row := _make_font_demo_row(
		"Hand",
		"Caveat · Ma Shan Zheng · 我做着不该做的梦,寂塔的方向起雾的时候会响。",
		ChromeTheme.font_handwriting(500),
		26
	)
	vbox.add_child(hw_row)

	_add_ink_rule(vbox)

	# Mono row (IBM Plex Mono + Noto Sans SC)
	var mono_row := _make_font_demo_row(
		"Mono",
		"IBM Plex Mono · Noto Sans SC · CACHE 92.9% · ¥0.023/min · 系统",
		ChromeTheme.font_mono(600),
		13
	)
	vbox.add_child(mono_row)

	_add_ink_rule(vbox)

	# KeyCap 行
	var keycap_hbox := HBoxContainer.new()
	keycap_hbox.add_theme_constant_override("separation", 6)
	vbox.add_child(keycap_hbox)

	for k in ["W", "A", "S", "D", "E", "Esc", "Tab", "1", "2", "3", "4"]:
		var cap := KeyCapScene.instantiate()
		cap.text = k
		keycap_hbox.add_child(cap)

	# 封蜡红圆点 + 备注
	var wax_hbox := HBoxContainer.new()
	wax_hbox.add_theme_constant_override("separation", 10)
	vbox.add_child(wax_hbox)

	var wax := PanelContainer.new()
	wax.add_theme_stylebox_override("panel", ChromeTheme.make_wax_seal())
	wax.custom_minimum_size = Vector2(14, 14)
	wax_hbox.add_child(wax)

	var wax_label := Label.new()
	wax_label.text = "封蜡红 #8B4513 — 强调点"
	wax_label.add_theme_font_override("font", ChromeTheme.font_mono(400))
	wax_label.add_theme_font_size_override("font_size", 11)
	wax_label.add_theme_color_override("font_color", ChromeTheme.COLOR_OAK_INK)
	wax_hbox.add_child(wax_label)

	# ---------------------------- 浮空 parchment 模拟 hover whisper ----------------------------
	var whisper := PanelContainer.new()
	whisper.add_theme_stylebox_override("panel", ChromeTheme.make_parchment_floating(0.78))
	whisper.position = Vector2(420, 510)
	add_child(whisper)

	var whisper_label := Label.new()
	whisper_label.text = "苏拂 · 擦酒馆门口的木牌"
	whisper_label.add_theme_font_override("font", ChromeTheme.font_serif(500))
	whisper_label.add_theme_font_size_override("font_size", 13)
	whisper_label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	whisper.add_child(whisper_label)

	# ---------------------------- 底部:说明文字 ----------------------------
	var footer := Label.new()
	footer.text = "F0 视觉地基检查 — 看到上面这些就证明字体 + chrome + KeyCap 都装好了。F1 会真正替换 HUD。"
	footer.add_theme_font_override("font", ChromeTheme.font_mono(400))
	footer.add_theme_font_size_override("font_size", 11)
	footer.add_theme_color_override("font_color", Color(0.7, 0.65, 0.55, 0.8))
	footer.position = Vector2(240, 670)
	footer.size = Vector2(800, 20)
	add_child(footer)


# ---------------------------- 辅助:一行字体 demo ----------------------------
func _make_font_demo_row(tag: String, sample: String, font: FontVariation, size: int) -> HBoxContainer:
	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 12)

	var tag_label := Label.new()
	tag_label.text = tag
	tag_label.add_theme_font_override("font", ChromeTheme.font_mono(600))
	tag_label.add_theme_font_size_override("font_size", 10)
	tag_label.add_theme_color_override("font_color", ChromeTheme.COLOR_OAK_INK)
	tag_label.custom_minimum_size = Vector2(48, 0)
	tag_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	hbox.add_child(tag_label)

	var sample_label := Label.new()
	sample_label.text = sample
	sample_label.add_theme_font_override("font", font)
	sample_label.add_theme_font_size_override("font_size", size)
	sample_label.add_theme_color_override("font_color", ChromeTheme.COLOR_DEEP_INK)
	hbox.add_child(sample_label)

	return hbox


func _add_ink_rule(parent: Node) -> void:
	var rule := PanelContainer.new()
	rule.add_theme_stylebox_override("panel", ChromeTheme.make_ink_rule())
	rule.custom_minimum_size = Vector2(0, 1)
	parent.add_child(rule)
