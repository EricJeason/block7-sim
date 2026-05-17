// rpg-modals.jsx — class-RPG container framework.
// C 角色面板 · I 背包 · J 任务/线索本 · P 角色图鉴
//
// Design principle (per v2.1 brief §8):
// Each container exposes a yaml-like schema so future user-authored 剧本/模组
// can inject data. UI shows current default state PLUS a "schema preview"
// strip on the right side of each panel so Eric can see the interface shape.

// ---------------- Reusable: full-screen heavy modal frame ----------------
function HeavyModal({ title, hint, hotkey, children, onClose, width = 1080, height = 620, schema }) {
  return (
    <>
      <div style={{
        position: 'absolute', inset: 0,
        background: 'rgba(26,20,16,0.78)',
        backdropFilter: 'blur(2px)'
      }} className="modalfade" />
      <div className="parchment modalfade" style={{
        position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        width, height,
        borderRadius: 4,
        padding: 0,
        boxShadow: '0 18px 48px rgba(0,0,0,0.6)',
        display: 'flex', flexDirection: 'column'
      }}>
        <CornerFlourish />
        {/* HEADER */}
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', padding: '20px 28px 12px', position: 'relative', zIndex: 1 }}>
          <div>
            <div className="serif" style={{ fontSize: 24, fontWeight: 600, color: '#3d2f1f', letterSpacing: '0.04em' }}>{title}</div>
            {hint && <div className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: '#6b5840', marginTop: 4 }}>{hint}</div>}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <KeyCap dim>{hotkey}</KeyCap>
            <span className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.18em', textTransform: 'uppercase' }}>关闭</span>
          </div>
        </div>
        <div className="ink-rule" style={{ marginInline: 28, position: 'relative', zIndex: 1 }} />
        {/* BODY (children + optional schema strip) */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative', zIndex: 1 }}>
          <div style={{ flex: 1, overflow: 'auto', padding: '18px 28px 24px' }}>
            {children}
          </div>
          {schema && (
            <div style={{
              width: 240, borderLeft: '1px dashed rgba(107,88,64,0.45)',
              padding: '18px 16px 20px 18px',
              background: 'rgba(107,88,64,0.04)'
            }}>
              <div className="mono" style={{ fontSize: 9, color: '#8b4513', letterSpacing: '0.18em', textTransform: 'uppercase' }}>剧本注入 · SCHEMA</div>
              <div className="mono" style={{ fontSize: 10, color: '#3d2f1f', lineHeight: 1.6, marginTop: 8, whiteSpace: 'pre-wrap' }}>
                {schema}
              </div>
              <div className="ink-rule" style={{ margin: '12px 0' }} />
              <div className="serif" style={{ fontSize: 12, fontStyle: 'italic', color: '#6b5840', lineHeight: 1.5 }}>
                未来玩家自定义剧本可以往此结构注入新字段,UI 自动适配。
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ---------------- C · Character Panel ----------------
function CharacterPanel({ npc = NPCS[3], onClose }) {
  return (
    <HeavyModal
      title="角色 · 你自己"
      hint="显性数值 + 半显症状 + 隐性属性(后端 only)"
      hotkey="C"
      onClose={onClose}
      schema={SCHEMA_C}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '256px 1fr', gap: 28 }}>
        {/* Portrait + name */}
        <div>
          <Portrait npc={npc} variant="normal" />
          <div className="serif" style={{ fontSize: 22, fontWeight: 600, color: '#3d2f1f', marginTop: 12 }}>{npc.name}</div>
          <div className="mono" style={{ fontSize: 11, color: '#6b5840', letterSpacing: '0.14em' }}>04 · {npc.role}</div>
          <div className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: '#6b5840', marginTop: 8, lineHeight: 1.5 }}>
            30 年前父亲在这里"殉职",她来调查真相。
          </div>
        </div>

        {/* Stats */}
        <div>
          {/* 显性 */}
          <SectionLabel>显性状态 · VISIBLE</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', columnGap: 24, rowGap: 10, marginTop: 8 }}>
            <StatBar label="健康" value={80} max={100} c="#7a9d6a" />
            <StatBar label="疲劳" value={30} max={100} c="#a07a4a" />
            <StatBar label="饥饿" value={40} max={100} c="#a06a3a" />
            <StatRow label="情绪" value="平静" />
          </div>

          {/* 半显 */}
          <SectionLabel style={{ marginTop: 22 }}>半显症状 · SEMI-VISIBLE</SectionLabel>
          <div className="serif" style={{ fontSize: 14, color: '#3d2f1f', marginTop: 6, lineHeight: 1.7 }}>
            <div>· 手指偶尔轻微颤抖</div>
            <div>· 最近做的梦很清晰</div>
            <div>· 闻到雨味会想起寂塔</div>
          </div>
          <div className="serif" style={{ fontSize: 12, fontStyle: 'italic', color: '#6b5840', marginTop: 6 }}>
            (玩家看见症状,看不见背后的数值。可能是感染度,可能是心理负荷。)
          </div>

          {/* 隐性 */}
          <SectionLabel style={{ marginTop: 22 }}>隐性属性 · HIDDEN(后端 only)</SectionLabel>
          <div className="mono inkbleed" style={{
            marginTop: 6,
            border: '1px dashed rgba(107,88,64,0.5)',
            padding: '10px 12px',
            background: 'rgba(107,88,64,0.05)',
            fontSize: 11, color: '#6b5840', lineHeight: 1.6
          }}>
            <span style={{ color: '#8b4513' }}>{`{`}</span> infection_progress: 0.42, trauma_load: 0.58,
            relations: {`{`} lin_qiu: 0.6, shen_yan: -0.2 {`}`},
            personality: {`{`} introvert: 0.7, curious: 0.9 {`}`}<span style={{ color: '#8b4513' }}>{`}`}</span>
            <div style={{ marginTop: 6, fontStyle: 'italic', color: '#6b5840', opacity: 0.85 }}>UI 永远不显示 · 仅 LLM 与系统使用</div>
          </div>

          {/* equipment */}
          <SectionLabel style={{ marginTop: 22 }}>装备摘要 · EQUIPMENT</SectionLabel>
          <div className="serif" style={{ fontSize: 14, color: '#3d2f1f', marginTop: 6, lineHeight: 1.7 }}>
            <div>· 父亲的旧背包 <span className="mono" style={{ color: '#8b4513', fontSize: 11 }}>+4 容量</span></div>
            <div>· 蓝色长裙 <span className="mono" style={{ color: '#6b5840', fontSize: 11 }}>无加成</span></div>
            <div>· 母亲的护身符 <span className="mono" style={{ color: '#7a5a96', fontSize: 11 }}>未知效果</span></div>
          </div>
          <div className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: '#6b5840', marginTop: 14 }}>
            6 / 10 格已用 · 详见背包 <KeyCap dim>I</KeyCap>
          </div>
        </div>
      </div>
    </HeavyModal>
  );
}

const SCHEMA_C = `visible_stats:
  - { id, name, max,
      current, color, icon? }

semi_visible_symptoms:
  - { id, text,
      condition }

hidden_attributes:
  - { id, value,
      drives: [behavior_tag] }

equipment_summary:
  - { slot, item_id,
      effect? }`;

function SectionLabel({ children, style }) {
  return (
    <div className="mono" style={{
      fontSize: 10, color: '#8b4513',
      letterSpacing: '0.18em', textTransform: 'uppercase',
      borderBottom: '1px solid rgba(107,88,64,0.4)',
      paddingBottom: 4,
      ...style
    }}>{children}</div>
  );
}

function StatBar({ label, value, max, c }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span className="serif" style={{ fontSize: 14, color: '#3d2f1f' }}>{label}</span>
        <span className="mono" style={{ fontSize: 11, color: '#6b5840' }}>{value} / {max}</span>
      </div>
      <div style={{
        height: 10,
        background: 'rgba(107,88,64,0.18)',
        border: '1px solid rgba(107,88,64,0.5)',
        marginTop: 3,
      }}>
        <div style={{ width: `${(value/max)*100}%`, height: '100%', background: c }} />
      </div>
    </div>
  );
}
function StatRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', height: '100%', paddingBottom: 2 }}>
      <span className="serif" style={{ fontSize: 14, color: '#3d2f1f' }}>{label}</span>
      <span className="serif" style={{ fontSize: 16, color: '#3d2f1f', fontWeight: 600 }}>{value}</span>
    </div>
  );
}

// ---------------- I · Inventory ----------------
const ITEMS = [
  { id: 'scroll',   name: '协会档案残页', icon: '📜', weight: 1, type: '文档',   desc: '写着一段被划掉的话——还能勉强辨认出「殉职」二字。', selected: false },
  { id: 'key',      name: '黄铜旧钥匙',   icon: '🔑', weight: 1, type: '工具',   desc: '父亲遗物。不知道开的是哪扇门。', selected: false },
  { id: 'herb1',    name: '霜花草 × 3',   icon: '🌿', weight: 1, type: '药材',   desc: '林秋说过,这种草最近开得比往年早。', selected: false },
  { id: 'herb2',    name: '苦根 × 2',     icon: '🌿', weight: 1, type: '药材',   desc: '苦但管用。捕魔队员人手一份。', selected: false },
  { id: 'amulet',   name: '母亲的护身符', icon: '💍', weight: 0, type: '装备',   desc: '陶土做的小符,内里嵌一颗发暗的石头。', selected: false },
  { id: 'note',     name: '父亲的笔记本', icon: '📓', weight: 1, type: '文档/线索', desc: '父亲在暮谷镇最后几天的随手记录。第 17-19 页被撕掉了。', selected: true },
];

function InventoryPanel({ player = NPCS[3], onClose }) {
  const used = ITEMS.reduce((s, it) => s + (it.weight || 0), 0);
  const max = 10;
  const selected = ITEMS.find(it => it.selected);

  return (
    <HeavyModal
      title="背包 · 持有物"
      hint="基础 6 + 父亲的旧背包 +4 · 当前无负重病"
      hotkey="I"
      onClose={onClose}
      schema={SCHEMA_I}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 1fr', gap: 28 }}>
        {/* LEFT — grid */}
        <div>
          <EncumbranceChip load={used} max={max} />

          <div style={{
            marginTop: 18,
            display: 'grid',
            gridTemplateColumns: 'repeat(5, 1fr)',
            gap: 6,
          }}>
            {Array.from({ length: max }, (_, i) => {
              const it = ITEMS[i];
              return (
                <div key={i} style={{
                  aspectRatio: '1 / 1',
                  background: 'rgba(232,220,196,0.7)',
                  border: '1px solid ' + (it?.selected ? '#8b4513' : 'rgba(107,88,64,0.55)'),
                  boxShadow: it?.selected ? 'inset 0 0 0 2px rgba(139,69,19,0.25)' : 'inset 0 1px 0 rgba(255,235,200,0.5)',
                  position: 'relative',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 28,
                  color: '#3d2f1f',
                  opacity: it ? 1 : 0.6,
                }}>
                  {it ? (
                    <>
                      <ItemGlyph kind={it.id} />
                      {it.weight > 1 && (
                        <span className="mono" style={{ position: 'absolute', right: 4, bottom: 2, fontSize: 9, color: '#6b5840' }}>×{it.weight}</span>
                      )}
                    </>
                  ) : (
                    <span className="mono" style={{ fontSize: 14, color: 'rgba(107,88,64,0.35)' }}>—</span>
                  )}
                </div>
              );
            })}
          </div>

          <div className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: '#6b5840', marginTop: 16 }}>
            {used} / {max} 格已用。剧本可注入更大背包 / 不同 slot 分区。
          </div>

          <div className="ink-rule" style={{ margin: '16px 0 12px' }} />
          <SectionLabel>NPC 也有背包 · 共享 primitive</SectionLabel>
          <div className="serif" style={{ fontSize: 13, color: '#3d2f1f', marginTop: 6, lineHeight: 1.5 }}>
            走近 NPC 时只能从外观推测他们的负重等级:
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 6 }}>
            <EncumbranceChip compact load={2} max={10} />
            <EncumbranceChip compact load={5} max={10} />
            <EncumbranceChip compact load={8} max={10} />
            <EncumbranceChip compact load={10} max={10} />
          </div>
        </div>

        {/* RIGHT — selected item detail */}
        <div>
          {selected && (
            <div className="parchment" style={{ position: 'relative', padding: 18, borderRadius: 3 }}>
              <CornerFlourish />
              <div style={{ display: 'flex', gap: 14, alignItems: 'center', position: 'relative', zIndex: 1 }}>
                <div style={{
                  width: 56, height: 56,
                  background: 'rgba(107,88,64,0.08)',
                  border: '1px solid rgba(107,88,64,0.55)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 32
                }}>
                  <ItemGlyph kind={selected.id} />
                </div>
                <div>
                  <div className="serif" style={{ fontSize: 18, fontWeight: 600, color: '#3d2f1f' }}>{selected.name}</div>
                  <div className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.14em', textTransform: 'uppercase' }}>
                    {selected.type} · 重量 {selected.weight}
                  </div>
                </div>
              </div>
              <div className="ink-rule" style={{ margin: '14px 0', position: 'relative', zIndex: 1 }} />
              <div className="serif" style={{ fontSize: 14, color: '#3d2f1f', lineHeight: 1.6, position: 'relative', zIndex: 1 }}>
                {selected.desc}
              </div>
              <div className="ink-rule" style={{ margin: '14px 0', position: 'relative', zIndex: 1 }} />
              <SectionLabel>可用操作</SectionLabel>
              <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap', position: 'relative', zIndex: 1 }}>
                {['阅读', '给予 NPC', '收为线索 →', '丢弃'].map((a, i) => (
                  <button key={i} className="serif" style={actionBtn}>{a}</button>
                ))}
              </div>
            </div>
          )}

          <div className="ink-rule" style={{ margin: '16px 0' }} />
          <SectionLabel>负重病 · 减容惩罚</SectionLabel>
          <div className="serif" style={{ fontSize: 13, color: '#3d2f1f', marginTop: 6, lineHeight: 1.6 }}>
            受伤 / 生病 / 过度疲劳时,部分格子会被锁定:
          </div>
          <div style={{
            marginTop: 8,
            display: 'grid', gridTemplateColumns: 'repeat(10, 1fr)', gap: 3,
          }}>
            {Array.from({ length: 10 }, (_, i) => (
              <div key={i} style={{
                aspectRatio: '1 / 1',
                background: i < 2 ? 'rgba(60,40,30,0.55)' : 'rgba(232,220,196,0.7)',
                border: '1px solid ' + (i < 2 ? '#3d2f1f' : 'rgba(107,88,64,0.55)'),
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: i < 2 ? '#8b4513' : 'transparent',
                fontFamily: 'monospace', fontSize: 14
              }}>{i < 2 ? '×' : ''}</div>
            ))}
          </div>
        </div>
      </div>
    </HeavyModal>
  );
}

const SCHEMA_I = `item:
  id, name, icon,
  weight, type
  description
  actions:
    [read, give, drop,
     use, equip, ...]
  effects?:
    on_use, on_equip
  hidden_tags?:
    ["father_relic", ...]`;

function ItemGlyph({ kind }) {
  const W = 36, H = 36;
  switch (kind) {
    case 'scroll': return (
      <svg width="32" height="32" viewBox="0 0 36 36">
        <rect x="6" y="10" width="24" height="18" fill="#e8dcc4" stroke="#6b5840" strokeWidth="1.5" />
        <line x1="9" y1="14" x2="27" y2="14" stroke="#6b5840" strokeWidth="0.6" />
        <line x1="9" y1="18" x2="24" y2="18" stroke="#6b5840" strokeWidth="0.6" />
        <line x1="9" y1="22" x2="27" y2="22" stroke="#6b5840" strokeWidth="0.6" />
        <line x1="12" y1="17" x2="20" y2="17" stroke="#3d2f1f" strokeWidth="2" />
      </svg>
    );
    case 'key': return (
      <svg width="32" height="32" viewBox="0 0 36 36">
        <circle cx="12" cy="18" r="6" fill="none" stroke="#a08550" strokeWidth="2" />
        <line x1="18" y1="18" x2="30" y2="18" stroke="#a08550" strokeWidth="2" />
        <line x1="26" y1="18" x2="26" y2="23" stroke="#a08550" strokeWidth="2" />
        <line x1="22" y1="18" x2="22" y2="22" stroke="#a08550" strokeWidth="2" />
      </svg>
    );
    case 'herb1': case 'herb2': return (
      <svg width="32" height="32" viewBox="0 0 36 36">
        <path d="M 18 6 Q 24 14 18 28 Q 12 14 18 6 Z" fill="#5a7340" stroke="#3a4f2a" strokeWidth="1" />
        <line x1="18" y1="10" x2="18" y2="26" stroke="#3a4f2a" strokeWidth="0.8" />
        <path d="M 18 16 L 14 14" stroke="#3a4f2a" strokeWidth="0.6" />
        <path d="M 18 18 L 22 16" stroke="#3a4f2a" strokeWidth="0.6" />
      </svg>
    );
    case 'amulet': return (
      <svg width="32" height="32" viewBox="0 0 36 36">
        <line x1="18" y1="6" x2="12" y2="14" stroke="#6b5840" strokeWidth="1" />
        <line x1="18" y1="6" x2="24" y2="14" stroke="#6b5840" strokeWidth="1" />
        <circle cx="18" cy="20" r="7" fill="#a07050" stroke="#6b5840" strokeWidth="1" />
        <circle cx="18" cy="20" r="3" fill="#3a3a48" />
      </svg>
    );
    case 'note': return (
      <svg width="32" height="32" viewBox="0 0 36 36">
        <rect x="8" y="6" width="20" height="24" fill="#5a3a1a" stroke="#3a1a08" strokeWidth="1" />
        <rect x="9" y="7" width="18" height="22" fill="#e8dcc4" />
        <line x1="11" y1="11" x2="25" y2="11" stroke="#6b5840" strokeWidth="0.5" />
        <line x1="11" y1="15" x2="22" y2="15" stroke="#6b5840" strokeWidth="0.5" />
        <line x1="11" y1="19" x2="24" y2="19" stroke="#6b5840" strokeWidth="0.5" />
        {/* torn-out pages */}
        <path d="M 11 23 L 13 25 L 15 23 L 17 25 L 19 23 L 21 25 L 23 23 L 25 25" stroke="#8b4513" strokeWidth="1" fill="none" />
      </svg>
    );
    default: return null;
  }
}

const actionBtn = {
  background: 'rgba(232,220,196,0.6)',
  border: '1px solid #6b5840',
  borderRadius: 2,
  color: '#3d2f1f',
  padding: '4px 12px',
  fontSize: 13,
  fontFamily: 'Cormorant Garamond, Noto Serif SC, serif',
  cursor: 'pointer'
};

// ---------------- J · Quest / Clue Book ----------------
function QuestBook({ onClose }) {
  const [tab, setTab] = React.useState('clues');
  return (
    <HeavyModal
      title={tab === 'clues' ? '线索 / 心愿' : '任务'}
      hint={tab === 'clues' ? '你自己的发现 · 软任务为主' : '硬任务 · 主要由剧本/模组注入'}
      hotkey="J"
      onClose={onClose}
      schema={SCHEMA_J}
    >
      {/* tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 14 }}>
        <Tab active={tab === 'clues'} onClick={() => setTab('clues')}>线索 / 心愿</Tab>
        <Tab active={tab === 'quests'} onClick={() => setTab('quests')}>任务</Tab>
      </div>

      {tab === 'clues' && <ClueTab />}
      {tab === 'quests' && <QuestTab />}
    </HeavyModal>
  );
}

function Tab({ active, onClick, children }) {
  return (
    <button onClick={onClick} className="serif" style={{
      background: active ? '#e8dcc4' : 'rgba(107,88,64,0.06)',
      border: '1px solid ' + (active ? '#6b5840' : 'rgba(107,88,64,0.3)'),
      borderBottom: active ? '1px solid #e8dcc4' : '1px solid #6b5840',
      padding: '7px 22px',
      fontSize: 14,
      color: active ? '#8b4513' : '#6b5840',
      fontWeight: active ? 600 : 500,
      letterSpacing: '0.06em',
      cursor: 'pointer',
      marginBottom: -1,
      position: 'relative', zIndex: active ? 1 : 0,
    }}>{children}</button>
  );
}

function ClueTab() {
  // Diary aesthetic — handwriting heavy, parchment
  const clues = [
    {
      day: 3, time: '14:20', source: '从苏拂处听说',
      handwriting: true,
      body: '“已经数到 7 个做相似梦的客人了……”',
      annotation: '你的记录:谁?',
      checks: [
        { label: '林秋', checked: true }, { label: '阿杏', checked: true },
        { label: '文姐', checked: true }, { label: '白嬤', checked: false },
        { label: '?', checked: false }, { label: '?', checked: false },
        { label: '?', checked: false },
      ],
    },
    {
      day: 2, time: '10:15', source: '从父亲笔记残页',
      handwriting: true,
      body: '“若大魔潮真的近了——我希望我还记得自己是谁。”',
      tags: ['寂塔遗迹', '母亲', '?'],
    },
    {
      day: 1, time: '19:30', source: '你自己观察到',
      handwriting: true,
      body: '暖谷的故乡小树开了一朵紫色的花。',
      note: '(文姐没说什么,但她绕开了树)',
    },
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
      {clues.map((c, i) => (
        <div key={i}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
            <span className="mono" style={{ fontSize: 10, color: '#8b4513', letterSpacing: '0.14em' }}>DAY {c.day} · {c.time}</span>
            <span className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: '#6b5840' }}>{c.source}</span>
          </div>
          <div className="ink-rule" style={{ margin: '6px 0 10px' }} />
          <div className="handwriting" style={{ fontSize: 22, color: '#3d2f1f', lineHeight: 1.4 }}>
            {c.body}
          </div>
          {c.note && (
            <div className="handwriting" style={{ fontSize: 18, color: '#6b5840', marginTop: 4, opacity: 0.85 }}>{c.note}</div>
          )}
          {c.checks && (
            <div style={{ marginTop: 10 }}>
              <div className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: '#6b5840' }}>{c.annotation}</div>
              <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 4 }}>
                {c.checks.map((ch, j) => (
                  <label key={j} className="handwriting" style={{ fontSize: 18, color: ch.checked ? '#3d2f1f' : '#6b5840', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                    <span style={{
                      display: 'inline-block', width: 12, height: 12,
                      border: '1.5px solid #6b5840',
                      background: ch.checked ? '#3d2f1f' : 'transparent',
                      position: 'relative'
                    }}>
                      {ch.checked && <span style={{ position: 'absolute', left: 1, top: -2, color: '#f4e6cf', fontSize: 12, fontFamily: 'Caveat, cursive' }}>✓</span>}
                    </span>
                    {ch.label}
                  </label>
                ))}
              </div>
            </div>
          )}
          {c.tags && (
            <div style={{ marginTop: 10, display: 'flex', gap: 6, alignItems: 'center' }}>
              <span className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: '#6b5840' }}>关联:</span>
              {c.tags.map((tg, j) => (
                <span key={j} className="serif" style={{
                  fontSize: 13, color: '#3d2f1f',
                  border: '1px dashed rgba(107,88,64,0.5)',
                  borderRadius: 2,
                  padding: '0 6px'
                }}>{tg}</span>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function QuestTab() {
  const quests = [
    { state: 'in_progress', title: '父亲笔记缺失的第 17-19 页', source: '剧本注入',
      steps: [
        { text: '调查父亲在暮谷镇的最后几天', done: true },
        { text: '找到撕掉那几页的人', done: false },
        { text: '决定是否当面对质', done: false },
      ]
    },
    { state: 'unaccepted', title: '苏拂的"七个做相似梦的客人"', source: '默认软任务 → 可升格' },
    { state: 'completed', title: '把田柱的刀送到沈砚手里', source: '剧本注入' },
  ];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {quests.map((q, i) => (
        <div key={i} className="parchment" style={{ position: 'relative', padding: 14, borderRadius: 3 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, position: 'relative', zIndex: 1 }}>
            <QuestStateBadge state={q.state} />
            <span className="serif" style={{ fontSize: 17, fontWeight: 600, color: '#3d2f1f' }}>{q.title}</span>
            <span style={{ flex: 1 }} />
            <span className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.14em', textTransform: 'uppercase' }}>{q.source}</span>
          </div>
          {q.steps && (
            <div style={{ marginTop: 10, position: 'relative', zIndex: 1 }}>
              {q.steps.map((s, j) => (
                <div key={j} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '2px 0' }}>
                  <span style={{
                    display: 'inline-block', width: 14, height: 14,
                    border: '1.5px solid #6b5840',
                    background: s.done ? '#3d2f1f' : 'transparent',
                    color: '#f4e6cf', fontSize: 11, fontFamily: 'monospace',
                    textAlign: 'center', lineHeight: '11px',
                  }}>{s.done ? '✓' : ''}</span>
                  <span className="serif" style={{ fontSize: 14, color: s.done ? '#6b5840' : '#3d2f1f', textDecoration: s.done ? 'line-through' : 'none' }}>
                    {s.text}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function QuestStateBadge({ state }) {
  const c = {
    unaccepted:  { bg: 'rgba(107,88,64,0.12)', fg: '#6b5840', t: '未接' },
    in_progress: { bg: 'rgba(139,69,19,0.15)', fg: '#8b4513', t: '进行中' },
    completed:   { bg: 'rgba(74,107,58,0.15)', fg: '#4a6b3a', t: '已完成' },
    failed:      { bg: 'rgba(80,30,30,0.15)',  fg: '#7a3030', t: '失败' },
  }[state];
  return (
    <span className="mono" style={{
      background: c.bg, color: c.fg,
      fontSize: 9, letterSpacing: '0.18em', textTransform: 'uppercase',
      padding: '2px 7px', borderRadius: 2,
      border: '1px solid ' + c.fg + '55'
    }}>{c.t}</span>
  );
}

const SCHEMA_J = `clue:  // 软,默认
  timestamp, source,
  body, annotations,
  tags?

quest:  // 硬,剧本注入
  id, title, description
  states:
    [unaccepted, in_progress,
     completed, failed]
  trigger:
    { condition, source_npc? }
  steps:
    [{ text, done? }, ...]
  reward?:
    { items, attribute_changes }`;

// ---------------- P · Codex ----------------
function CodexPanel({ onClose }) {
  const [selected, setSelected] = React.useState(0);

  const codex = NPCS.map(n => {
    // unlock level: 0 see, 1 talked, 2 deep
    const level = (
      n.id === 6 ? 3 :       // qianling: deep
      n.id === 1 ? 2 :       // linqiu: talked deep
      n.id === 10 ? 2 :
      n.id === 3 ? 2 :
      n.id === 8 ? 0 :       // majiu: never
      1
    );
    return { npc: n, level };
  });

  const cur = codex[selected];
  const isUnlocked = cur.npc.id !== 4 && cur.level > 0;
  const isPlayer = cur.npc.id === 4;

  return (
    <HeavyModal
      title="角色图鉴 · 12 人"
      hint="渐进解锁 · 看见 / 对话过 / 深入了解 · 三个圆点显示你对此人的认知程度"
      hotkey="P"
      onClose={onClose}
      schema={SCHEMA_P}
      width={1100}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 24, height: '100%' }}>
        {/* LEFT — list */}
        <div style={{
          borderRight: '1px solid rgba(107,88,64,0.3)',
          paddingRight: 14,
          maxHeight: 480, overflowY: 'auto'
        }}>
          {codex.map((c, i) => (
            <div key={c.npc.id} onClick={() => setSelected(i)} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '6px 8px',
              borderRadius: 2,
              background: i === selected ? 'rgba(139,69,19,0.12)' : 'transparent',
              border: '1px solid ' + (i === selected ? 'rgba(139,69,19,0.45)' : 'transparent'),
              cursor: 'pointer'
            }}>
              <span className="mono" style={{ fontSize: 10, color: '#8b4513', minWidth: 16 }}>{String(c.npc.id).padStart(2,'0')}</span>
              <span className="serif" style={{ fontSize: 15, color: c.npc.id === 4 ? '#8b4513' : '#3d2f1f', fontWeight: i === selected ? 600 : 500 }}>
                {c.npc.name}
              </span>
              <span style={{ flex: 1 }} />
              {c.npc.id === 4 ? (
                <span className="mono" style={{ fontSize: 9, color: '#8b4513', letterSpacing: '0.16em' }}>YOU</span>
              ) : (
                <UnlockDots level={c.level} />
              )}
            </div>
          ))}
        </div>

        {/* RIGHT — detail */}
        <div>
          {isPlayer ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 12 }}>
              <Portrait npc={cur.npc} size={220} />
              <div className="serif" style={{ fontSize: 16, fontStyle: 'italic', color: '#6b5840' }}>这是你自己。详见角色面板 <KeyCap dim>C</KeyCap></div>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: '256px 1fr', gap: 20 }}>
              {/* portrait */}
              <div>
                <Portrait npc={cur.npc} size={256} variant={cur.level === 0 ? 'normal' : 'normal'} />
                <div className="serif" style={{ fontSize: 22, fontWeight: 600, color: '#3d2f1f', marginTop: 10 }}>
                  {cur.npc.name}
                </div>
                <div className="mono" style={{ fontSize: 11, color: '#6b5840', letterSpacing: '0.14em' }}>
                  {String(cur.npc.id).padStart(2,'0')} · {cur.npc.role}
                </div>
                <UnlockBar level={cur.level} />
              </div>
              <div>
                <SectionLabel>常去</SectionLabel>
                <div className="serif" style={{ fontSize: 14, color: '#3d2f1f', marginTop: 6 }}>
                  {cur.level >= 1 ? '北霜工坊 · 老松广场' : <Lock />}
                </div>

                <SectionLabel style={{ marginTop: 14 }}>关系网摘要</SectionLabel>
                <div className="serif" style={{ fontSize: 14, color: '#3d2f1f', marginTop: 6, lineHeight: 1.7 }}>
                  {cur.level >= 2 ? (
                    <>
                      <div>· 暗中暗恋于:<Locked text="???" /></div>
                      <div>· 师父于:阿杏</div>
                    </>
                  ) : <Lock />}
                </div>

                <SectionLabel style={{ marginTop: 14 }}>你听说过的事</SectionLabel>
                <div className="serif" style={{ fontSize: 14, color: '#3d2f1f', marginTop: 6, lineHeight: 1.7 }}>
                  {cur.level >= 1 ? (
                    <>
                      <div>· 8 年前曾大病一场,治好了</div>
                      <div>· 跟文姐很要好(苏拂提)</div>
                      {cur.level >= 2 && <div>· 最近经常发呆(阿杏提)</div>}
                    </>
                  ) : <Lock />}
                </div>

                <SectionLabel style={{ marginTop: 14 }}>你直接看见的事</SectionLabel>
                <div className="serif" style={{ fontSize: 14, color: '#3d2f1f', marginTop: 6, lineHeight: 1.7 }}>
                  {cur.level >= 1 ? (
                    <>
                      <div>· 多次在井边打水</div>
                      <div>· 跟你说过 {cur.level >= 2 ? '3' : '1'} 次话</div>
                      {cur.level >= 2 && <div>· 似乎对寂塔方向特别关注</div>}
                    </>
                  ) : <Lock />}
                </div>

                <SectionLabel style={{ marginTop: 14 }}>未解锁字段</SectionLabel>
                <div className="serif" style={{ fontSize: 14, color: '#6b5840', marginTop: 6, display: 'flex', gap: 18 }}>
                  <Locked text="??? · 秘密" />
                  <Locked text="??? · 童年" />
                  <Locked text="??? · 真名" />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </HeavyModal>
  );
}

function UnlockDots({ level }) {
  return (
    <span style={{ display: 'inline-flex', gap: 2 }}>
      {[0,1,2].map(i => (
        <span key={i} style={{
          width: 6, height: 6, borderRadius: '50%',
          background: i < level ? '#8b4513' : 'transparent',
          border: '1px solid ' + (i < level ? '#8b4513' : 'rgba(107,88,64,0.55)')
        }} />
      ))}
    </span>
  );
}
function UnlockBar({ level }) {
  const labels = ['见过', '对话过', '深入了解'];
  return (
    <div style={{ marginTop: 10, display: 'flex', gap: 4, alignItems: 'center' }}>
      {labels.map((l, i) => (
        <span key={i} className="mono" style={{
          fontSize: 9, letterSpacing: '0.12em', textTransform: 'uppercase',
          color: i < level ? '#8b4513' : '#6b5840',
          background: i < level ? 'rgba(139,69,19,0.12)' : 'transparent',
          border: '1px solid ' + (i < level ? 'rgba(139,69,19,0.45)' : 'rgba(107,88,64,0.3)'),
          padding: '1px 5px', borderRadius: 2,
        }}>{l}</span>
      ))}
    </div>
  );
}
function Lock() {
  return (
    <span className="serif" style={{ fontSize: 16, fontStyle: 'italic', color: '#6b5840', letterSpacing: '0.3em' }}>
      ? ? ?
    </span>
  );
}
function Locked({ text }) {
  return (
    <span className="serif" style={{
      fontSize: 14, fontStyle: 'italic', color: '#6b5840',
      letterSpacing: '0.18em',
      padding: '0 4px',
      background: 'rgba(107,88,64,0.06)',
      borderRadius: 2
    }}>{text}</span>
  );
}

const SCHEMA_P = `npc_codex:
  id, name, role, portrait
  unlock_levels:
    0 → 见过
    1 → 对话过
    2 → 深入了解
  fields:
    - { id, unlock_condition,
        renderer: text|list|tag }
  locked_placeholder:
    "???"

  // 剧本可注入新 fields
  // condition 字段控制
  // 玩家何时能解锁`;

window.CharacterPanel = CharacterPanel;
window.InventoryPanel = InventoryPanel;
window.QuestBook = QuestBook;
window.CodexPanel = CodexPanel;
window.HeavyModal = HeavyModal;
window.SectionLabel = SectionLabel;
