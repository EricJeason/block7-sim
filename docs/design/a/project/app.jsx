// app.jsx — design canvas wiring all artboards together.

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "location": "plaza",
  "hour": 15,
  "day": 3,
  "atmosphere": "normal",
  "healerHint": true,
  "showCracks": false
}/*EDITMODE-END*/;

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  return (
    <>
      <DesignCanvas>
        {/* ============= 1. INTERACTIVE MAIN SCREEN ============= */}
        <DCSection
          id="main-screen"
          title="S3 · 主屏(可玩原型)"
          subtitle="WASD 移动 · 走近 NPC 头顶 whisper(NPC名 · action + 负重 chip) · E 气泡菜单 · C 角色 · I 背包 · J 线索 · P 图鉴 · F 读心 · R 关系网 · Q 场所概览 · T 大事日志 · Esc 菜单 · Tab 暂停"
        >
          <DCArtboard id="main-plaza" label={`老松广场 · DAY ${t.day} · ${pad(t.hour)}:52`} width={1280} height={720}>
            <MainScreen
              initialLoc={t.location}
              day={t.day}
              hour={t.hour}
              minute={52}
              atmosphere={t.atmosphere}
              showHealerHint={t.healerHint}
              showCracks={t.showCracks}
            />
          </DCArtboard>
        </DCSection>

        {/* ============= 2. HUD CHROME ============= */}
        <DCSection
          id="hud-chrome"
          title="HUD chrome · 元件"
          subtitle="常驻屏幕的极简元件:顶部木板时钟、E 互动气泡、场所标签、键位提示"
        >
          <DCArtboard id="clock-strip" label="木板时钟 · 四时辰" width={1080} height={300}>
            <ClockStrip />
          </DCArtboard>

          <DCArtboard id="e-bubble" label="E · 头顶气泡菜单" width={480} height={420}>
            <BubbleMenuShowcase />
          </DCArtboard>

          <DCArtboard id="location-label" label="左下场所标签 · 右下键位" width={1080} height={300}>
            <LocationStrip />
          </DCArtboard>
        </DCSection>

        {/* ============= 3. MODAL SURFACES ============= */}
        <DCSection
          id="modals"
          title="Modal 三层"
          subtitle="重量沉浸 (78% 黑遮罩 · 打断走路) · 轻量信息 (半屏卡片) · 系统功能 (侧栏滑入)"
        >
          <DCArtboard id="q-card" label="Q · 场所概览 · 轻量卡片" width={1280} height={720}>
            <PreviewWith location="plaza">
              <LocationCard
                loc={LOCATIONS.plaza}
                npcs={NPCS}
                day={3} hour={15} minute={52}
                onClose={() => {}}
              />
            </PreviewWith>
          </DCArtboard>

          <DCArtboard id="esc-menu" label="Esc · 系统菜单 · 侧栏" width={1280} height={720}>
            <PreviewWith location="plaza" dim>
              <SystemMenu day={3} hour={15} minute={52} onClose={() => {}} />
            </PreviewWith>
          </DCArtboard>

          <DCArtboard id="f-heart" label="F · S4 读自己的心 · 重量沉浸" width={1280} height={720}>
            <PreviewWith location="plaza" dim>
              <InnerHeart
                playerNpc={NPCS[3]}
                reflections={[
                  { text: '昨夜又梦见配药材。手很稳,却记不得是为谁配的。' },
                  { text: '父亲的笔记里有一页被撕掉了——我一直没敢问母亲。' },
                  { text: '寂塔的方向,起雾的时候会响。' },
                  { text: '若大魔潮真的近了——我希望我还记得自己是谁。' },
                ]}
                onClose={() => {}}
              />
            </PreviewWith>
          </DCArtboard>

          <DCArtboard id="t-log" label="T · 大事日志 · 侧栏" width={1280} height={720}>
            <PreviewWith location="plaza">
              <EventLog events={EVENTS} day={3} onClose={() => {}} />
            </PreviewWith>
          </DCArtboard>

          <DCArtboard id="s11-dialogue" label="S11 · 对话 · LLM 候选 + 自由输入混合" width={1280} height={720}>
            <PreviewWith location="plaza" dim>
              <DialogueSession
                player={NPCS[3]}
                npc={NPCS[0]}
                lines={{
                  current: '“你今早去过井边吗?我看着水有些发暗——也许只是错觉。”',
                  choices: [
                    '“你最近也睡得不安稳吧。”',
                    '“没什么,我应该回去看看温棚。”',
                    '(沉默地点头)',
                  ]
                }}
                onClose={() => {}}
              />
            </PreviewWith>
          </DCArtboard>

          <DCArtboard id="s5-network" label="S5 · 关系网 · 三态观察(0/灰虚/紫实)" width={1280} height={720}>
            <PreviewWith location="plaza" dim>
              <RelationshipNetwork npcs={NPCS} player={NPCS[3]} onClose={() => {}} />
            </PreviewWith>
          </DCArtboard>
        </DCSection>

        {/* ============= 3b. CLASS-RPG CONTAINERS ============= */}
        <DCSection
          id="containers"
          title="类 RPG 容器框架 · C / I / J / P"
          subtitle="给未来玩家剧本/模组系统的标准化数据接入点 · 每个容器右侧的虚线条带是注入 schema"
        >
          <DCArtboard id="c-character" label="C · 角色面板 · 显性 + 半显 + 隐性 三层" width={1280} height={720}>
            <PreviewWith location="plaza" dim>
              <CharacterPanel npc={NPCS[3]} onClose={() => {}} />
            </PreviewWith>
          </DCArtboard>

          <DCArtboard id="i-inventory" label="I · 背包 · 玩家 + NPC 共享 primitive" width={1280} height={720}>
            <PreviewWith location="plaza" dim>
              <InventoryPanel player={NPCS[3]} onClose={() => {}} />
            </PreviewWith>
          </DCArtboard>

          <DCArtboard id="j-questbook" label="J · 线索 / 任务本 · 双 tab" width={1280} height={720}>
            <PreviewWith location="plaza" dim>
              <QuestBook onClose={() => {}} />
            </PreviewWith>
          </DCArtboard>

          <DCArtboard id="p-codex" label="P · 角色图鉴 · 渐进解锁(见过/对话过/深入)" width={1280} height={720}>
            <PreviewWith location="plaza" dim>
              <CodexPanel onClose={() => {}} />
            </PreviewWith>
          </DCArtboard>
        </DCSection>

        {/* ============= 3c. TOUCH ADAPTATION ============= */}
        <DCSection
          id="touch"
          title="触控适配 · B 平板原型"
          subtitle="键盘提示替换为虚拟摇杆 + 折叠菜单。所有面板内容与桌面端同源,只是入口形态不同"
        >
          <DCArtboard id="touch-s3" label="S3 主屏 · 触控版" width={1280} height={720}>
            <TouchMainScreen />
          </DCArtboard>
        </DCSection>

        {/* ============= 4. SCENES WITH ANCHORS ============= */}
        <DCSection
          id="anchors"
          title="4 场所 · NPC 站位锚点"
          subtitle="每场 5-10 个语义锚点。LLM 生成的 action 映射到对应锚点,不用 4×3 网格。"
        >
          {Object.values(LOCATIONS).map(loc => (
            <DCArtboard key={loc.id} id={'anchor-'+loc.id} label={loc.name + ' · ' + loc.anchors.length + ' 锚点'} width={1280} height={720}>
              <AnchorMap loc={loc} />
            </DCArtboard>
          ))}
        </DCSection>

        {/* ============= 5. NPC SPRITE STYLE + PORTRAITS ============= */}
        <DCSection
          id="sprites"
          title="NPC · sprite + portrait + 状态变体"
          subtitle="walking sprite 待美术升级到 64×128 anime-pixel · 256×256 portrait 是代码占位,待样图替换 · 每 NPC 3 状态:正常 / 感染 / 治愈者潜在"
        >
          <DCArtboard id="portrait-linqiu" label="01 林秋 · portrait · 正常 / 感染 / 治愈者标记" width={1180} height={420}>
            <PortraitTriptych npc={NPCS[0]} />
          </DCArtboard>
          <DCArtboard id="portrait-qianling" label="06 千绫 · portrait · 正常 / 感染 / 治愈者标记" width={1180} height={420}>
            <PortraitTriptych npc={NPCS[5]} />
          </DCArtboard>
          <DCArtboard id="sprite-linqiu" label="01 林秋 · walking sprite · 4 朝向(占位)" width={620} height={200}>
            <SpriteCard npc={NPCS[0]} />
          </DCArtboard>
          <DCArtboard id="sprite-qianling" label="06 千绫 · walking sprite · 4 朝向(占位)" width={620} height={200}>
            <SpriteCard npc={NPCS[5]} />
          </DCArtboard>
          <DCArtboard id="sprite-roster" label="12 人 · 色板 + 占位 sprite" width={1280} height={520}>
            <NPCRoster />
          </DCArtboard>
          <DCArtboard id="art-note" label="美术接入说明" width={620} height={320}>
            <ArtHandoffNote />
          </DCArtboard>
        </DCSection>

        {/* ============= 6. PROPOSALS — HEALER HINT ============= */}
        <DCSection
          id="healer-hint"
          title="提案 · 治愈者的克制视觉暗示"
          subtitle="不能直接写「已感染:是」。给玩家「拼出来」的可能,不是「告诉他」。三个候选,Eric 选 / 混合。"
        >
          <DCArtboard id="hint-glow" label="A · 名牌冷紫晕(常驻 · 极淡)" width={620} height={420}>
            <HealerProposalGlow />
          </DCArtboard>
          <DCArtboard id="hint-dream" label="B · 夜晚梦境碎片粒子(条件触发)" width={620} height={420}>
            <HealerProposalDream />
          </DCArtboard>
          <DCArtboard id="hint-bubble" label="C · 对话气泡的双重描边(对话时才看见)" width={620} height={420}>
            <HealerProposalBubble />
          </DCArtboard>
        </DCSection>

        {/* ============= 7. PROPOSALS — LOOMING ATMOSPHERE ============= */}
        <DCSection
          id="atmosphere"
          title="提案 · 大魔潮临近的氛围反馈"
          subtitle="玩家「感觉哪里不对」而非「看到警示」。提供两条路线,可以叠加。"
        >
          <DCArtboard id="atm-coolshift" label="A · 屏幕色温随日推移渐冷" width={1180} height={520}>
            <AtmosphereColorShift />
          </DCArtboard>
          <DCArtboard id="atm-cracks" label="B · 木板时钟边缘微裂 + 故乡小树异色开花" width={1180} height={520}>
            <AtmosphereCracks />
          </DCArtboard>
        </DCSection>

        {/* ============= 8. DESIGN SYSTEM REFERENCE ============= */}
        <DCSection
          id="system"
          title="设计系统 · 速查"
          subtitle="本规范是 Godot 4 桌面版与平板原型的共同视觉源头"
        >
          <DCArtboard id="palette" label="色板 · 字体 · 间距" width={1280} height={520}>
            <DesignTokens />
          </DCArtboard>
          <DCArtboard id="keymap" label="快捷键全表 · 14 项" width={1080} height={620}>
            <KeymapTable />
          </DCArtboard>
        </DCSection>
      </DesignCanvas>

      {/* ----------- TWEAKS PANEL (toolbar toggle) ----------- */}
      <TweaksPanel title="主屏 · 调参">
        <TweakSection label="场所">
          <TweakRadio
            label="当前场所"
            value={t.location}
            onChange={v => setTweak('location', v)}
            options={[
              { value: 'plaza', label: '老松广场' },
              { value: 'forge', label: '北霜工坊' },
              { value: 'farm', label: '暖谷农场' },
              { value: 'tower', label: '寂塔遗迹' },
            ]}
          />
        </TweakSection>

        <TweakSection label="时间">
          <TweakSlider
            label="时辰 (24h)"
            value={t.hour}
            onChange={v => setTweak('hour', v)}
            min={0} max={23} step={1}
          />
          <TweakSlider
            label="第几天"
            value={t.day}
            onChange={v => setTweak('day', v)}
            min={1} max={30} step={1}
          />
        </TweakSection>

        <TweakSection label="氛围">
          <TweakRadio
            label="大魔潮临近度"
            value={t.atmosphere}
            onChange={v => setTweak('atmosphere', v)}
            options={[
              { value: 'normal', label: '平静' },
              { value: 'looming', label: '渐冷' },
              { value: 'dusk', label: '黄昏' },
              { value: 'night', label: '深夜' },
            ]}
          />
          <TweakToggle label="治愈者名牌冷紫晕" value={t.healerHint} onChange={v => setTweak('healerHint', v)} />
          <TweakToggle label="时钟边缘微裂" value={t.showCracks} onChange={v => setTweak('showCracks', v)} />
        </TweakSection>
      </TweaksPanel>
    </>
  );
}

// ----------- helpers used by artboards -----------

function pad(n) { return String(n).padStart(2, '0'); }

function PreviewWith({ location = 'plaza', dim, children }) {
  return (
    <div style={{ position: 'relative', width: 1280, height: 720, background: '#1a140c', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0 }}>
        <Scene id={location} />
      </div>
      {dim && (
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(26,20,16,0.35)' }} />
      )}
      {/* still show clock */}
      <div style={{ position: 'absolute', top: -4, left: '50%', transform: 'translateX(-50%)', zIndex: 5 }}>
        <WoodClock day={3} hour={15} minute={52} />
      </div>
      {children}
    </div>
  );
}

function ClockStrip() {
  const items = [
    { hour: 8,  minute: 12, day: 1, label: 'MORNING · 6:00–11:00 · 朝阳',  cracked: false },
    { hour: 13, minute: 0,  day: 5, label: 'NOON · 11:00–17:00 · 烈日',     cracked: false },
    { hour: 18, minute: 47, day: 12, label: 'DUSK · 17:00–20:00 · 黄昏',    cracked: true  },
    { hour: 23, minute: 4,  day: 22, label: 'NIGHT · 20:00–06:00 · 月亮 + 裂纹', cracked: true },
  ];
  return (
    <div style={{
      width: '100%', height: '100%',
      background: '#1a140c',
      display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 0,
      alignItems: 'start', padding: '32px 24px 24px',
      boxSizing: 'border-box',
      backgroundImage:
        'radial-gradient(circle at 50% 0%, rgba(245,225,170,0.05), transparent 60%)',
    }}>
      {items.map((it, i) => (
        <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
          <div style={{ position: 'relative', marginTop: -4 }}>
            <WoodClock day={it.day} hour={it.hour} minute={it.minute} cracked={it.cracked} />
          </div>
          <div className="mono" style={{ color: 'rgba(232,220,196,0.65)', fontSize: 10, letterSpacing: '0.18em' }}>
            {it.label}
          </div>
        </div>
      ))}
    </div>
  );
}

function BubbleMenuShowcase() {
  return (
    <div style={{ width: '100%', height: '100%', background: '#1a140c', position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0 }}><Scene id="plaza" /></div>
      <div style={{ position: 'absolute', inset: 0, background: 'rgba(26,20,16,0.45)' }} />

      <div style={{
        position: 'absolute',
        left: '50%', top: '52%', transform: 'translate(-50%,-50%)'
      }}>
        <div style={{ position: 'relative' }}>
          <BubbleMenu
            npc={NPCS[0]}
            selected={1}
            options={[
              { label: '打招呼' },
              { label: '读心', cost: '× 限 1' },
              { label: '离开' },
            ]}
          />
          <div style={{
            position: 'absolute', left: '50%', top: 'calc(100% + 18px)', transform: 'translateX(-50%)',
            zIndex: -1,
          }}>
            <PixelSprite npc={NPCS[0]} dir="s" scale={4} />
          </div>
        </div>
      </div>

      {/* annotations */}
      <div className="mono" style={anno({ left: 22, top: 22 })}>
        ↓ 气泡从最近 NPC 头顶弹出,方向键 / 鼠标选择,Enter / 点击确认。
      </div>
      <div className="mono" style={anno({ right: 22, top: 130 })}>
        “*” → 有限次/有代价
      </div>
      <div className="mono" style={anno({ left: 22, bottom: 22 })}>
        羊皮纸底 · 旧橡木墨边 · 圆角 4px · 14-16px Cormorant
      </div>
    </div>
  );
}

function LocationStrip() {
  return (
    <div style={{ width: '100%', height: '100%', background: '#1a140c', position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', inset: 0 }}><Scene id="plaza" /></div>
      <div style={{ position: 'absolute', left: 32, bottom: 28 }}>
        <LocationLabel name="老松广场" en="Old Pine Plaza" count={4} />
      </div>
      <div style={{ position: 'absolute', right: 32, bottom: 28 }}>
        <KeyHints hints={[
          { key: 'E', label: '靠近 NPC 互动' },
          { key: 'Q', label: '场所概览' },
          { key: 'F', label: '读自己的心' },
          { key: 'Esc', label: '菜单' },
        ]} />
      </div>
      <div className="mono" style={anno({ left: 32, top: 22 })}>
        ↘ Cormorant 30px · 墨 #6B5840 · 0.85 透明
      </div>
      <div className="mono" style={anno({ right: 32, top: 22 })}>
        ↘ Plex Mono 11px · 键帽 7×11
      </div>
    </div>
  );
}

function AnchorMap({ loc }) {
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden', background: '#1a140c' }}>
      <Scene id={loc.id} />
      {/* anchor markers */}
      {loc.anchors.map((a, i) => (
        <div key={a.id} style={{ position: 'absolute', left: a.x, top: a.y, transform: 'translate(-50%,-50%)' }}>
          <div style={{
            width: 14, height: 14, borderRadius: '50%',
            background: '#8b4513',
            border: '2px solid #f4e6cf',
            boxShadow: '0 0 0 1px #6b5840, 0 4px 10px rgba(0,0,0,0.5)'
          }} />
          <div style={{
            position: 'absolute', left: 18, top: -4,
            whiteSpace: 'nowrap',
            background: 'rgba(232,220,196,0.92)',
            border: '1px solid #6b5840',
            color: '#3d2f1f',
            padding: '1px 6px', borderRadius: 2,
            fontFamily: 'Cormorant Garamond, Noto Serif SC, serif',
            fontSize: 13,
            boxShadow: '0 2px 6px rgba(0,0,0,0.4)'
          }}>
            <span className="mono" style={{ fontSize: 9, color: '#8b4513', letterSpacing: '0.16em', marginRight: 6 }}>{pad(i+1)}</span>
            {a.label}
            <span className="mono" style={{ fontSize: 9, color: '#6b5840', marginLeft: 8 }}>
              ({a.x},{a.y})
            </span>
          </div>
        </div>
      ))}
      {/* title */}
      <div className="parchment" style={{
        position: 'absolute', left: 28, top: 28,
        padding: '14px 18px', borderRadius: 3,
        maxWidth: 320
      }}>
        <div className="serif" style={{ fontSize: 22, fontWeight: 600, color: '#3d2f1f' }}>{loc.name}</div>
        <div className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.18em', textTransform: 'uppercase', marginTop: 2 }}>{loc.en}</div>
        <div className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: '#6b5840', marginTop: 8 }}>{loc.mood}</div>
      </div>
    </div>
  );
}

function SpriteCard({ npc }) {
  return (
    <div style={{ width: '100%', height: '100%', background: '#f0eee9', padding: '28px 32px', boxSizing: 'border-box' }}>
      <SpriteSheetRow npc={npc} label />
      <div className="ink-rule" style={{ margin: '20px 0 12px' }} />
      <div className="mono" style={{ fontSize: 11, color: '#6b5840', letterSpacing: '0.1em' }}>
        14×22 像素 · 4× 放大渲染 · image-rendering: pixelated · 投影 ellipse
      </div>
    </div>
  );
}

function NPCRoster() {
  return (
    <div style={{ padding: 28, background: '#f0eee9', height: '100%', boxSizing: 'border-box' }}>
      <div className="mono" style={{ fontSize: 11, color: '#6b5840', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 16 }}>
        12 NPCS · color tokens + idle sprites
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 24 }}>
        {NPCS.map(n => (
          <div key={n.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div style={{ position: 'relative', marginBottom: 6 }}>
              <PixelSprite npc={n} dir="s" scale={3} />
              {n.healer && (
                <div title="治愈者" style={{
                  position: 'absolute', top: -4, right: -10,
                  width: 12, height: 12, borderRadius: '50%',
                  background: 'radial-gradient(circle, #c8a4d4, #7a5a96)',
                  boxShadow: '0 0 8px rgba(122,90,150,0.7)'
                }} />
              )}
            </div>
            <div className="serif" style={{ fontSize: 16, fontWeight: 600, color: '#3d2f1f' }}>
              <span style={{ color: '#8b4513', marginRight: 4 }}>{pad(n.id)}</span>{n.name}
            </div>
            <div className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.06em', marginTop: 2 }}>{n.role}</div>
            <div className="mono" style={{ fontSize: 9, color: '#6b5840', opacity: 0.6, marginTop: 4 }}>{n.color}</div>
          </div>
        ))}
      </div>
      <div className="ink-rule" style={{ margin: '20px 0 10px' }} />
      <div className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: '#6b5840' }}>
        紫晕标记 = 治愈者(玩家在游戏内不直接看见这个标记;这里只是给 Eric 看)。
      </div>
    </div>
  );
}

function HealerProposalGlow() {
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden', background: '#1a140c' }}>
      <Scene id="plaza" />
      <div style={{ position: 'absolute', left: '30%', top: '60%', transform: 'translate(-50%,-100%)' }}>
        <NameTag npc={NPCS[0]} hint="在井边打水" showHealerHint />
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: 4 }}>
          <PixelSprite npc={NPCS[0]} dir="s" scale={4} />
        </div>
      </div>
      <div style={{ position: 'absolute', left: '65%', top: '70%', transform: 'translate(-50%,-100%)' }}>
        <NameTag npc={NPCS[4]} hint="坐在议事厅前的台阶上" showHealerHint />
        <div style={{ display: 'flex', justifyContent: 'center', marginTop: 4 }}>
          <PixelSprite npc={NPCS[4]} dir="s" scale={4} />
        </div>
      </div>
      <div className="parchment" style={{
        position: 'absolute', left: 20, bottom: 20, right: 20,
        padding: '12px 16px', borderRadius: 3
      }}>
        <div className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.18em', textTransform: 'uppercase' }}>A · 治愈者名牌冷紫晕</div>
        <div className="serif" style={{ fontSize: 14, color: '#3d2f1f', marginTop: 4 }}>
          名牌描边由旧橡木墨变为冷紫(rgba(122,90,150,0.55))。常驻,但极淡——玩家走过多人后才会"觉得不对劲"。
          <span style={{ color: '#8b4513' }}> 此图中:林秋、沈砚展示紫晕(沈砚为对照说明,实际剧情中他不是治愈者)。</span>
        </div>
      </div>
    </div>
  );
}
function HealerProposalDream() {
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden', background: '#0e0a08' }}>
      <Scene id="farm" />
      <NightOverlayStandalone />
      <div style={{ position: 'absolute', left: '30%', top: '62%', transform: 'translate(-50%,-100%)' }}>
        <div style={{ position: 'relative' }}>
          <span className="dreamparticle" style={{ left: '40%', animationDelay: '0.2s' }} />
          <span className="dreamparticle" style={{ left: '55%', animationDelay: '1.5s' }} />
          <span className="dreamparticle" style={{ left: '50%', animationDelay: '2.8s' }} />
          <PixelSprite npc={NPCS[1]} dir="s" scale={4} />
        </div>
      </div>
      <div style={{ position: 'absolute', left: '60%', top: '70%', transform: 'translate(-50%,-100%)' }}>
        <div style={{ position: 'relative' }}>
          <span className="dreamparticle" style={{ left: '45%', animationDelay: '0.8s' }} />
          <span className="dreamparticle" style={{ left: '55%', animationDelay: '2.2s' }} />
          <PixelSprite npc={NPCS[0]} dir="s" scale={4} />
        </div>
      </div>
      <div className="parchment" style={{
        position: 'absolute', left: 20, bottom: 20, right: 20,
        padding: '12px 16px', borderRadius: 3
      }}>
        <div className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.18em', textTransform: 'uppercase' }}>B · 夜晚的梦境碎片</div>
        <div className="serif" style={{ fontSize: 14, color: '#3d2f1f', marginTop: 4 }}>
          仅在 22:00–06:00 时段、治愈者 NPC idle 状态下,头顶随机间隔飘起 1 颗淡紫粒子(0.5–3s 周期),持续 ≤ 1s。玩家很可能错过,但反复几日后会"注意到":阿杏和林秋夜里都做同一种梦?
        </div>
      </div>
    </div>
  );
}
function HealerProposalBubble() {
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden', background: '#1a140c' }}>
      <Scene id="plaza" />
      <div style={{ position: 'absolute', inset: 0, background: 'rgba(26,20,16,0.4)' }} />
      <div style={{
        position: 'absolute', left: '50%', top: '40%', transform: 'translate(-50%, 0)',
        display: 'flex', gap: 40
      }}>
        <div className="parchment" style={{
          padding: '12px 16px', borderRadius: 4, position: 'relative',
          width: 240,
          boxShadow:
            'inset 0 0 0 1px rgba(107,88,64,0.6), inset 0 0 0 3px rgba(122,90,150,0.45), 0 4px 16px rgba(0,0,0,0.5)'
        }}>
          <div className="serif" style={{ fontSize: 13, color: '#6b5840', fontStyle: 'italic', position: 'relative', zIndex: 1 }}>林秋(治愈者)</div>
          <div className="serif" style={{ fontSize: 15, color: '#3d2f1f', marginTop: 4, position: 'relative', zIndex: 1 }}>
            “昨夜雨下得不大,药圃倒积了水。”
          </div>
        </div>
        <div className="parchment" style={{
          padding: '12px 16px', borderRadius: 4, position: 'relative',
          width: 240,
        }}>
          <div className="serif" style={{ fontSize: 13, color: '#6b5840', fontStyle: 'italic', position: 'relative', zIndex: 1 }}>千绫(非治愈者 · 对照)</div>
          <div className="serif" style={{ fontSize: 15, color: '#3d2f1f', marginTop: 4, position: 'relative', zIndex: 1 }}>
            “巡逻的网绳又磨损了一条。”
          </div>
        </div>
      </div>
      <div className="parchment" style={{
        position: 'absolute', left: 20, bottom: 20, right: 20,
        padding: '12px 16px', borderRadius: 3
      }}>
        <div className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.18em', textTransform: 'uppercase' }}>C · 对话气泡的双重描边</div>
        <div className="serif" style={{ fontSize: 14, color: '#3d2f1f', marginTop: 4 }}>
          只有进入对话(S11)时才暴露:治愈者的气泡在墨边内侧多一道极淡的紫色 inset(3px,55% 不透明)。玩家与多个 NPC 对话后才会发现这条规律。
          <span style={{ color: '#8b4513' }}>权衡:克制感最强,但需要玩家与每个 NPC 对话才能积累线索。</span>
        </div>
      </div>
    </div>
  );
}
function NightOverlayStandalone() {
  return <div style={{
    position: 'absolute', inset: 0, pointerEvents: 'none',
    background: 'linear-gradient(180deg, rgba(20,20,50,0.55), rgba(10,10,30,0.55))',
    mixBlendMode: 'multiply'
  }} />;
}

function AtmosphereColorShift() {
  const days = [
    { day: 1, label: 'DAY 1 · 平静',       atmosphere: 'normal' },
    { day: 12, label: 'DAY 12 · 隐约',     atmosphere: 'looming-mild' },
    { day: 24, label: 'DAY 24 · 渐冷',     atmosphere: 'looming' },
  ];
  return (
    <div style={{ width: '100%', height: '100%', background: '#1a140c', padding: 24, boxSizing: 'border-box' }}>
      <div className="mono" style={{ fontSize: 11, color: 'rgba(232,220,196,0.65)', letterSpacing: '0.18em', marginBottom: 14 }}>
        A · 屏幕色温 + 雾的频率 + 远山饱和度 随日推进微调
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {days.map((d, i) => (
          <div key={i} style={{ position: 'relative', overflow: 'hidden', borderRadius: 4, border: '1px solid #6b5840', height: 320 }}>
            <Scene id="plaza" />
            {d.atmosphere === 'looming-mild' && (
              <div style={{
                position: 'absolute', inset: 0, pointerEvents: 'none',
                background: 'linear-gradient(180deg, rgba(120,110,140,0.10), rgba(80,70,90,0.10))',
                mixBlendMode: 'multiply'
              }} />
            )}
            {d.atmosphere === 'looming' && <LoomingOverlayStandalone />}
            <div className="mono" style={{
              position: 'absolute', left: 12, top: 12,
              fontSize: 10, color: 'rgba(245,235,200,0.85)',
              letterSpacing: '0.18em',
              background: 'rgba(20,12,4,0.5)', padding: '3px 8px', borderRadius: 2
            }}>{d.label}</div>
          </div>
        ))}
      </div>
      <div className="serif" style={{ fontSize: 14, fontStyle: 'italic', color: 'rgba(232,220,196,0.7)', marginTop: 14 }}>
        三档色温位移,每 5–7 日切一档。每帧偏移 ≤ 4%,玩家看单帧感觉不到,看连续几日的截图对比才"觉得不对劲"。
      </div>
    </div>
  );
}
function LoomingOverlayStandalone() {
  return (
    <>
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'linear-gradient(180deg, rgba(50,40,80,0.18) 0%, rgba(40,30,60,0.10) 60%, rgba(20,10,30,0.18) 100%)',
        mixBlendMode: 'multiply'
      }} />
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 50% 30%, rgba(180,170,200,0.18), transparent 70%)'
      }} />
    </>
  );
}
function AtmosphereCracks() {
  return (
    <div style={{ width: '100%', height: '100%', background: '#1a140c', padding: 24, boxSizing: 'border-box', position: 'relative' }}>
      <div className="mono" style={{ fontSize: 11, color: 'rgba(232,220,196,0.65)', letterSpacing: '0.18em', marginBottom: 14 }}>
        B · 物件级微变 · 时钟边缘的裂纹 + 故乡小树的异色开花
      </div>
      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
          <div className="mono" style={{ fontSize: 10, color: 'rgba(232,220,196,0.55)', letterSpacing: '0.18em', marginBottom: 8 }}>
            木板时钟 · DAY 1 → DAY 24
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center' }}>
            <WoodClock day={1} hour={9} minute={0} />
            <WoodClock day={12} hour={9} minute={0} cracked={false} />
            <WoodClock day={24} hour={9} minute={0} cracked />
          </div>
          <div className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: 'rgba(232,220,196,0.7)', marginTop: 10, textAlign: 'center' }}>
            DAY 20 起,边缘起 0.6px 裂纹。从不形成完整裂缝——玩家放大看才看得见。
          </div>
        </div>
        <div style={{ flex: 1 }}>
          <div className="mono" style={{ fontSize: 10, color: 'rgba(232,220,196,0.55)', letterSpacing: '0.18em', marginBottom: 8 }}>
            暖谷农场 · 故乡小树
          </div>
          <div style={{ position: 'relative', height: 320, border: '1px solid #6b5840', overflow: 'hidden', borderRadius: 4 }}>
            <Scene id="farm" />
            <div className="mono" style={{
              position: 'absolute', left: 12, top: 12,
              fontSize: 10, color: 'rgba(245,235,200,0.85)',
              letterSpacing: '0.18em',
              background: 'rgba(20,12,4,0.5)', padding: '3px 8px', borderRadius: 2
            }}>开了不该开的花</div>
            {/* arrow pointing at the tree */}
            <svg style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none">
              <line x1="62" y1="22" x2="55" y2="32" stroke="#f4e6cf" strokeWidth="0.3" />
            </svg>
            <div style={{
              position: 'absolute', left: '50%', top: '38%',
              width: 14, height: 14, borderRadius: '50%',
              border: '2px solid #f4e6cf',
              boxShadow: '0 0 14px rgba(244,230,207,0.6)'
            }} />
          </div>
          <div className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: 'rgba(232,220,196,0.7)', marginTop: 10 }}>
            DAY 1 无花 → DAY 7 1 朵 → DAY 14 3 朵 → DAY 21 满树。颜色:#c8a4d4(冷紫),不是植物群应有的色相。
          </div>
        </div>
      </div>
      <div className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: 'rgba(232,220,196,0.65)', marginTop: 16 }}>
        建议两个提案叠加使用:屏幕级的色温 + 物件级的微变。两条线索的玩家发现率不同,提升"自己拼出来"的成就感。
      </div>
    </div>
  );
}

function DesignTokens() {
  const swatches = [
    { hex: '#E8DCC4', label: '羊皮纸暖底', usage: 'panel / 容器底' },
    { hex: '#6B5840', label: '旧橡木墨',   usage: '边框 · 深色文字' },
    { hex: '#3D2F1F', label: '深咖墨',     usage: '主要正文' },
    { hex: '#8B4513', label: '封蜡红',     usage: '警示 · 关键按钮' },
    { hex: '#7A5A96', label: '冷紫(治愈者)', usage: '克制提示 only' },
    { hex: '#1A1410', label: 'Modal 遮罩 78%', usage: 'S4 / S5 / S11 全屏' },
  ];
  const types = [
    { name: 'Cormorant Garamond', fb: 'Noto Serif SC', family: '"Cormorant Garamond","Noto Serif SC",serif', sample: '老松广场 · 第三日,十五时' },
    { name: 'Caveat',             fb: 'Ma Shan Zheng', family: '"Caveat","Ma Shan Zheng",cursive',      sample: '昨夜又梦见配药材。手很稳。', className: 'handwriting' },
    { name: 'IBM Plex Mono',      fb: 'Noto Sans SC',  family: '"IBM Plex Mono","Noto Sans SC",monospace', sample: 'DAY 3 · 15:52 · 4 HERE' },
  ];
  return (
    <div style={{ width: '100%', height: '100%', background: '#f0eee9', padding: 28, boxSizing: 'border-box', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32 }}>
      <div>
        <div className="mono" style={{ fontSize: 11, color: '#6b5840', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 14 }}>色板</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {swatches.map(s => (
            <div key={s.hex} style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{ width: 60, height: 60, background: s.hex, border: '1px solid #6b5840', borderRadius: 3, flexShrink: 0 }} />
              <div>
                <div className="serif" style={{ fontSize: 18, fontWeight: 600, color: '#3d2f1f' }}>{s.label}</div>
                <div className="mono" style={{ fontSize: 11, color: '#6b5840' }}>{s.hex} · {s.usage}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="mono" style={{ fontSize: 11, color: '#6b5840', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 14 }}>字体三组</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {types.map(t => (
            <div key={t.name}>
              <div className="mono" style={{ fontSize: 11, color: '#6b5840', letterSpacing: '0.06em' }}>{t.name} + {t.fb}</div>
              <div className={t.className || 'serif'} style={{ fontSize: 28, color: '#3d2f1f', marginTop: 4, fontFamily: t.family }}>
                {t.sample}
              </div>
            </div>
          ))}
        </div>

        <div className="ink-rule" style={{ margin: '20px 0' }} />
        <div className="mono" style={{ fontSize: 11, color: '#6b5840', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 8 }}>间距 · 圆角</div>
        <div className="mono" style={{ fontSize: 12, color: '#3d2f1f', lineHeight: 1.6 }}>
          padding: 14/18/22/28<br />
          border-radius: 2 (tag) · 3 (panel) · 4 (modal) · 5 (bubble)<br />
          stroke: 1px hairline ink (#6B5840)<br />
          shadow: 0 6px 24px rgba(40,28,16,0.35)
        </div>
      </div>
    </div>
  );
}

// ----------- portrait triptych: 正常 / 感染 / 治愈者 -----------
function PortraitTriptych({ npc }) {
  const variants = [
    { v: 'normal',         label: '正常态',     hint: '日常 · 默认渲染' },
    { v: 'infected',       label: '感染态',     hint: '红眼 · 苍白 · 衣物破损' },
    { v: 'healer-marked',  label: '治愈者潜在', hint: '体貌与正常态相同 · 仅环境光晕 · 玩家肉眼几乎看不出' },
  ];
  return (
    <div style={{ width: '100%', height: '100%', background: '#f0eee9', padding: 28, boxSizing: 'border-box' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', gap: 16 }}>
        <div className="serif" style={{ fontSize: 24, fontWeight: 600, color: '#3d2f1f' }}>
          <span style={{ color: '#8b4513', marginRight: 6 }}>{String(npc.id).padStart(2,'0')}</span>{npc.name}
        </div>
        <div className="serif" style={{ fontSize: 15, fontStyle: 'italic', color: '#6b5840' }}>{npc.role}</div>
        <span style={{ flex: 1 }} />
        <div className="mono" style={{ fontSize: 10, color: '#8b4513', letterSpacing: '0.18em', textTransform: 'uppercase', padding: '3px 8px', border: '1px dashed rgba(139,69,19,0.45)', background: 'rgba(139,69,19,0.05)' }}>
          256×256 · ART TBD · 占位
        </div>
      </div>
      <div className="ink-rule" style={{ margin: '14px 0 18px' }} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 22 }}>
        {variants.map(v => (
          <div key={v.v} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
            <Portrait npc={npc} variant={v.v} size={240} />
            <div className="serif" style={{ fontSize: 18, fontWeight: 600, color: '#3d2f1f' }}>{v.label}</div>
            <div className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: '#6b5840', textAlign: 'center', maxWidth: 240, lineHeight: 1.4 }}>{v.hint}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ----------- handoff note -----------
function ArtHandoffNote() {
  return (
    <div style={{ width: '100%', height: '100%', background: '#f0eee9', padding: 28, boxSizing: 'border-box' }}>
      <div className="mono" style={{ fontSize: 11, color: '#8b4513', letterSpacing: '0.18em', textTransform: 'uppercase' }}>美术接入说明 · ART HANDOFF</div>
      <div className="ink-rule" style={{ margin: '10px 0 14px' }} />
      <div className="serif" style={{ fontSize: 15, color: '#3d2f1f', lineHeight: 1.6 }}>
        <div>· walking sprite 目标:<b>64×128</b> anime-pixel,4 朝向 + idle</div>
        <div>· portrait 目标:<b>256×256</b> bust shot</div>
        <div>· 每 NPC 3 状态:<b>正常 / 感染 / 治愈者潜在</b></div>
        <div>· 当前代码占位仅展示<b>视觉位置 + schema</b>,待样图替换</div>
      </div>
      <div className="ink-rule" style={{ margin: '14px 0' }} />
      <div className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: '#6b5840', lineHeight: 1.6 }}>
        Eric · 请把 3 张艾琳样图贴到对话,我会把它们作为 ground truth 替换林秋 + 千绫的 portrait,然后扩展 sprite 渲染管线。
      </div>
    </div>
  );
}

// ----------- TOUCH MAIN SCREEN (tablet S3) -----------
function TouchMainScreen() {
  const [menuOpen, setMenuOpen] = React.useState(false);
  return (
    <div style={{ width: 1280, height: 720, position: 'relative', overflow: 'hidden', background: '#1a140c' }}>
      <Scene id="plaza" />
      {/* clock */}
      <div style={{ position: 'absolute', top: -4, left: '50%', transform: 'translateX(-50%)' }}>
        <WoodClock day={3} hour={15} minute={52} />
      </div>
      {/* sample NPC sprites at anchors */}
      {NPCS.filter(n => n.loc === 'plaza').slice(0, 4).map((n, i) => {
        const a = LOCATIONS.plaza.anchors[i];
        return (
          <div key={n.id} style={{ position: 'absolute', left: a.x, top: a.y, transform: 'translate(-50%,-100%)' }}>
            <PixelSprite npc={n} dir="s" scale={4} />
          </div>
        );
      })}
      {/* player */}
      <div style={{ position: 'absolute', left: 620, top: 540, transform: 'translate(-50%,-100%)' }}>
        <PlayerSprite npc={NPCS[3]} dir="s" scale={4} />
      </div>

      {/* location label */}
      <div style={{ position: 'absolute', left: 32, bottom: 220 }}>
        <LocationLabel name="老松广场" en="Old Pine Plaza" count={4} />
      </div>

      {/* LEFT BOTTOM · virtual joystick */}
      <div style={{ position: 'absolute', left: 60, bottom: 60 }}>
        <div style={{
          width: 140, height: 140, borderRadius: '50%',
          background: 'rgba(232,220,196,0.18)',
          border: '2px solid rgba(232,220,196,0.45)',
          backdropFilter: 'blur(4px)',
          position: 'relative',
          boxShadow: '0 6px 24px rgba(0,0,0,0.5), inset 0 0 0 1px rgba(0,0,0,0.3)'
        }}>
          {/* directional ticks */}
          {['N','S','E','W'].map((d, i) => (
            <span key={d} className="mono" style={{
              position: 'absolute',
              left: d === 'E' ? 'auto' : d === 'W' ? 6 : '50%',
              right: d === 'E' ? 6 : 'auto',
              top:  d === 'S' ? 'auto' : d === 'N' ? 6 : '50%',
              bottom: d === 'S' ? 6 : 'auto',
              transform: (d === 'N' || d === 'S') ? 'translateX(-50%)' : 'translateY(-50%)',
              fontSize: 10, color: 'rgba(232,220,196,0.55)', letterSpacing: '0.2em'
            }}>{d}</span>
          ))}
          {/* thumb */}
          <div style={{
            position: 'absolute',
            left: '50%', top: '50%',
            transform: 'translate(-50%, -50%)',
            width: 64, height: 64, borderRadius: '50%',
            background: 'rgba(232,220,196,0.85)',
            border: '2px solid #6b5840',
            boxShadow: '0 3px 10px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.5)'
          }} />
        </div>
        <div className="mono" style={{ fontSize: 10, color: 'rgba(232,220,196,0.65)', letterSpacing: '0.18em', textTransform: 'uppercase', marginTop: 8, textAlign: 'center' }}>
          摇杆 · 或 TAP 地面
        </div>
      </div>

      {/* RIGHT BOTTOM · big E button (interact, tap NPC = same) */}
      <div style={{ position: 'absolute', right: 90, bottom: 90, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
        <button style={{
          width: 96, height: 96, borderRadius: '50%',
          background: 'radial-gradient(circle at 35% 30%, #d6a26a, #8b4513)',
          border: '3px solid #3d2f1f',
          boxShadow: '0 8px 24px rgba(0,0,0,0.55), inset 0 -4px 0 rgba(0,0,0,0.2), inset 0 2px 0 rgba(255,235,200,0.45)',
          fontFamily: '"Cormorant Garamond", serif', fontWeight: 600,
          fontSize: 32, color: '#f4e6cf',
          cursor: 'pointer',
        }}>互动</button>
        <div className="mono" style={{ fontSize: 10, color: 'rgba(232,220,196,0.65)', letterSpacing: '0.18em', textTransform: 'uppercase' }}>
          TAP 互动 · 或直接点 NPC
        </div>
      </div>

      {/* TOP RIGHT · hamburger -> expanded panel */}
      <div style={{ position: 'absolute', top: 60, right: 24, zIndex: 60 }}>
        {!menuOpen ? (
          <button onClick={() => setMenuOpen(true)} style={{
            width: 56, height: 56, borderRadius: 6,
            background: 'rgba(232,220,196,0.85)',
            border: '2px solid #6b5840',
            cursor: 'pointer', padding: 0,
            boxShadow: '0 4px 14px rgba(0,0,0,0.4)'
          }}>
            <div style={{ width: 26, height: 2, background: '#3d2f1f', margin: '5px auto' }} />
            <div style={{ width: 26, height: 2, background: '#3d2f1f', margin: '5px auto' }} />
            <div style={{ width: 26, height: 2, background: '#3d2f1f', margin: '5px auto' }} />
          </button>
        ) : (
          <div className="parchment" style={{
            position: 'relative',
            padding: '12px 10px', borderRadius: 6,
            minWidth: 240,
            display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6
          }}>
            {[
              { k:'C', l:'角色' }, { k:'I', l:'背包' }, { k:'J', l:'线索' },
              { k:'P', l:'图鉴' }, { k:'F', l:'读心' }, { k:'R', l:'关系' },
              { k:'Q', l:'此地' }, { k:'T', l:'日志' }, { k:'M', l:'地图' },
            ].map(b => (
              <div key={b.k} style={{
                background: 'rgba(232,220,196,0.7)',
                border: '1px solid #6b5840',
                borderRadius: 4,
                padding: '8px 4px',
                textAlign: 'center',
                position: 'relative', zIndex: 1
              }}>
                <div className="mono" style={{ fontSize: 13, fontWeight: 600, color: '#8b4513' }}>{b.k}</div>
                <div className="serif" style={{ fontSize: 13, color: '#3d2f1f' }}>{b.l}</div>
              </div>
            ))}
            <button onClick={() => setMenuOpen(false)} className="mono" style={{
              gridColumn: '1 / -1',
              background: 'transparent',
              border: '1px solid rgba(107,88,64,0.55)',
              borderRadius: 3,
              color: '#6b5840',
              padding: '4px',
              fontSize: 10, letterSpacing: '0.18em',
              cursor: 'pointer',
              position: 'relative', zIndex: 1,
              fontFamily: 'IBM Plex Mono, monospace'
            }}>合 上 · CLOSE</button>
          </div>
        )}
      </div>

      {/* annotation */}
      <div className="mono" style={{
        position: 'absolute', right: 24, bottom: 24,
        fontSize: 10, color: 'rgba(232,220,196,0.7)',
        letterSpacing: '0.16em',
        background: 'rgba(20,12,4,0.55)',
        padding: '4px 10px', borderRadius: 2,
        maxWidth: 280
      }}>
        触控版:左摇杆走路 / TAP NPC 互动 / 右上 ☰ 折叠面板入口。<br />Esc / Tab 键改为 ☰ 内的「菜单 · 暂停」按钮。
      </div>
    </div>
  );
}

// ----------- Full keymap table -----------
function KeymapTable() {
  const rows = [
    ['WASD',  '移动',           '—',          'v0.2', '走' ],
    ['E',     '与最近 NPC 互动', '头顶气泡菜单', 'v0.2', '互动'],
    ['C',     '角色面板(自己)','全屏沉浸',   'v0.3', '自己'],
    ['I',     '背包',           '全屏沉浸',   'v0.3', '自己'],
    ['J',     '任务 / 线索本',  '全屏沉浸',   'v0.4', '世界'],
    ['P',     '角色图鉴',       '全屏沉浸',   'v0.4', '世界'],
    ['F',     '读自己的心(S4)','全屏沉浸',   'v0.4', '自己'],
    ['R',     '关系网(S5)',    '全屏沉浸',   'v0.4', '世界'],
    ['T',     '大事日志(S13)', '侧栏滑入',   'v0.5', '世界'],
    ['Q',     '场所概览',       '半屏卡片',   'v0.3', '世界'],
    ['M',     '全屏地图(S8)', '全屏沉浸',   'v0.3', '世界'],
    ['Tab',   '暂停',           '—',          'v0.3', '系统'],
    ['Esc',   '系统菜单(S12)', '侧栏',       'v0.3', '系统'],
    ['1-4',   'debug 传送场所', '—',          'v0.2', 'debug'],
  ];
  const groupColor = {
    '走':     '#6b5840',
    '互动':   '#8b4513',
    '自己':   '#4a6b3a',
    '世界':   '#5a6fa0',
    '系统':   '#7a5a96',
    'debug':  '#a06a3a',
  };
  return (
    <div style={{ width: '100%', height: '100%', background: '#f0eee9', padding: '28px 36px', boxSizing: 'border-box' }}>
      <div className="mono" style={{ fontSize: 11, color: '#6b5840', letterSpacing: '0.18em', textTransform: 'uppercase' }}>
        KEYBOARD · 14 entries · 信息屏共 8 个(C/I/J/P/F/R/T/Q)
      </div>
      <div className="ink-rule" style={{ margin: '10px 0 16px' }} />
      <table style={{ width: '100%', borderCollapse: 'collapse', fontFamily: '"Cormorant Garamond","Noto Serif SC",serif' }}>
        <thead>
          <tr>
            <th style={th}>键</th>
            <th style={th}>行为</th>
            <th style={th}>UI 类型</th>
            <th style={th}>实装版本</th>
            <th style={th}>分组</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} style={{ borderBottom: '1px solid rgba(107,88,64,0.18)' }}>
              <td style={tdKey}><KeyCap>{r[0]}</KeyCap></td>
              <td style={td}>{r[1]}</td>
              <td style={tdMono}>{r[2]}</td>
              <td style={tdMono}>{r[3]}</td>
              <td style={td}>
                <span className="mono" style={{
                  fontSize: 9, letterSpacing: '0.16em', textTransform: 'uppercase',
                  padding: '2px 8px', borderRadius: 2,
                  color: groupColor[r[4]],
                  background: groupColor[r[4]] + '20',
                  border: '1px solid ' + groupColor[r[4]] + '55'
                }}>{r[4]}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="ink-rule" style={{ margin: '16px 0 10px' }} />
      <div className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: '#6b5840' }}>
        分组遵循「自己 / 世界 / 系统」三个心智模型 · 触控版把右栏键位替换为 ☰ 折叠面板。
      </div>
    </div>
  );
}
const th = { textAlign: 'left', padding: '6px 8px', fontSize: 11, color: '#8b4513', fontFamily: 'IBM Plex Mono, monospace', letterSpacing: '0.16em', textTransform: 'uppercase', borderBottom: '1px solid rgba(107,88,64,0.4)', fontWeight: 600 };
const td    = { padding: '8px 8px', fontSize: 14, color: '#3d2f1f' };
const tdKey = { padding: '8px 8px', width: 70 };
const tdMono = { padding: '8px 8px', fontSize: 12, fontFamily: 'IBM Plex Mono, monospace', color: '#6b5840', letterSpacing: '0.04em' };

const anno = (pos) => ({
  position: 'absolute',
  fontSize: 10, color: 'rgba(232,220,196,0.7)',
  letterSpacing: '0.14em',
  background: 'rgba(20,12,4,0.55)',
  padding: '3px 8px', borderRadius: 2,
  maxWidth: 260, lineHeight: 1.5,
  ...pos
});

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
