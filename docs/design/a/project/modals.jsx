// modals.jsx — Q, Esc, F (S4), T, M, S5, S11 modal/panel surfaces.
// "Heavy immersive" = full-screen 78% black scrim.
// "Light info"     = half-screen card or sidebar, no scrim.
// "System"         = sidebar slide-in, light scrim.

// ---------------- Q · location overview card (half-screen, no full scrim) ----------------
function LocationCard({ loc, npcs, day, hour, minute, onClose }) {
  const here = npcs.filter(n => n.loc === loc.id);
  const exits = ['北 → 暖谷农场', '东 → 北霜工坊', '南 → 寂塔遗迹方向'];
  return (
    <div style={{
      position: 'absolute', top: 70, right: 28,
      width: 376,
      borderRadius: 4,
      filter: 'drop-shadow(0 12px 32px rgba(20,10,4,0.5))'
    }} className="modalfade">
      <div className="parchment" style={{ position: 'relative', padding: '20px 22px 18px', borderRadius: 4 }}>
        {/* corner ink flourish */}
        <CornerFlourish />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
          <div style={{ position: 'relative', zIndex: 1 }}>
            <div className="serif" style={{ fontSize: 26, fontWeight: 600, color: '#3d2f1f', letterSpacing: '0.04em' }}>{loc.name}</div>
            <div className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.16em', textTransform: 'uppercase', marginTop: 2 }}>{loc.en}</div>
          </div>
          <button onClick={onClose} className="mono" style={cornerBtn}>Q · 关闭</button>
        </div>

        <div className="serif" style={{ fontSize: 13, fontStyle: 'italic', color: '#6b5840', marginTop: 8, position: 'relative', zIndex: 1 }}>
          {loc.mood}
        </div>

        <div className="ink-rule" style={{ margin: '14px 0 10px', position: 'relative', zIndex: 1 }} />

        <div className="mono" style={{
          fontSize: 10, color: '#6b5840', letterSpacing: '0.16em', textTransform: 'uppercase',
          marginBottom: 6, position: 'relative', zIndex: 1
        }}>此地 · {here.length} 人</div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, position: 'relative', zIndex: 1 }}>
          {here.map(n => (
            <div key={n.id} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '4px 6px', borderRadius: 3,
              background: 'rgba(107,88,64,0.06)'
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: 2,
                background: n.color,
                boxShadow: n.healer ? '0 0 0 1px rgba(122,90,150,0.6)' : 'none'
              }} />
              <span className="serif" style={{ fontSize: 14, color: '#3d2f1f' }}>{n.name}</span>
              <span className="serif" style={{ fontSize: 11, color: '#6b5840', fontStyle: 'italic', marginLeft: 'auto' }}>{n.role}</span>
            </div>
          ))}
        </div>

        <div className="ink-rule" style={{ margin: '14px 0 10px', position: 'relative', zIndex: 1 }} />

        <div className="mono" style={{
          fontSize: 10, color: '#6b5840', letterSpacing: '0.16em', textTransform: 'uppercase',
          marginBottom: 6, position: 'relative', zIndex: 1
        }}>出口</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, position: 'relative', zIndex: 1 }}>
          {exits.map((e, i) => (
            <div key={i} className="serif" style={{ fontSize: 14, color: '#3d2f1f', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ color: '#8b4513' }}>›</span>{e}
            </div>
          ))}
        </div>

        <div className="ink-rule" style={{ margin: '14px 0 10px', position: 'relative', zIndex: 1 }} />

        <div style={{ display: 'flex', justifyContent: 'space-between', position: 'relative', zIndex: 1 }}>
          <div>
            <div className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.16em', textTransform: 'uppercase' }}>今日天气</div>
            <div className="serif" style={{ fontSize: 14, color: '#3d2f1f' }}>晴 · 微风</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.16em', textTransform: 'uppercase' }}>DAY {day}</div>
            <div className="mono" style={{ fontSize: 14, color: '#3d2f1f' }}>{String(hour).padStart(2,'0')}:{String(minute).padStart(2,'0')}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------- Esc · system sidebar ----------------
function SystemMenu({ onClose, day, hour, minute }) {
  const items = [
    { label: '继续游戏', hint: 'Esc',  primary: true },
    { label: '保存进度', hint: '' },
    { label: '读取存档', hint: '' },
    { label: '设置',     hint: '' },
    { label: '剧本档案', hint: '', tag: '敬请期待', disabled: true },
    { label: '日志档案', hint: 'T' },
    { label: '地图',     hint: 'M' },
    { label: '回到主菜单', hint: '' },
  ];
  return (
    <>
      <div style={{
        position: 'absolute', inset: 0,
        background: 'rgba(26,20,16,0.45)',
        backdropFilter: 'blur(1px)'
      }} className="modalfade" />
      <div className="parchment modalfade" style={{
        position: 'absolute', right: 0, top: 0, bottom: 0,
        width: 316,
        padding: '34px 26px 28px',
        borderRadius: 0,
        boxShadow: '-12px 0 32px rgba(10,6,2,0.5), inset 1px 0 0 #6b5840',
      }}>
        <CornerFlourish />
        <div className="serif" style={{ fontSize: 22, fontWeight: 600, color: '#3d2f1f', letterSpacing: '0.06em', position: 'relative', zIndex: 1 }}>
          暂停 · 安息片刻
        </div>
        <div className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.18em', marginTop: 4, textTransform: 'uppercase', position: 'relative', zIndex: 1 }}>
          DAY {day} · {String(hour).padStart(2,'0')}:{String(minute).padStart(2,'0')} · PAUSED
        </div>
        <div className="ink-rule" style={{ margin: '18px 0', position: 'relative', zIndex: 1 }} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, position: 'relative', zIndex: 1 }}>
          {items.map((it, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '10px 12px',
              borderRadius: 3,
              background: it.primary ? 'rgba(139,69,19,0.10)' : 'transparent',
              border: it.primary ? '1px solid rgba(139,69,19,0.45)' : '1px solid transparent',
              cursor: it.disabled ? 'not-allowed' : 'pointer',
              opacity: it.disabled ? 0.55 : 1
            }}>
              <span className="serif" style={{
                fontSize: 17,
                color: it.primary ? '#8b4513' : '#3d2f1f',
                letterSpacing: '0.04em',
                fontWeight: it.primary ? 600 : 500
              }}>{it.label}</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {it.tag && (
                  <span className="mono" style={{
                    fontSize: 9, color: '#8b4513', letterSpacing: '0.16em', textTransform: 'uppercase',
                    border: '1px dashed rgba(139,69,19,0.45)', padding: '1px 6px', borderRadius: 2,
                    background: 'rgba(139,69,19,0.06)'
                  }}>{it.tag}</span>
                )}
                {it.hint && <KeyCap dim>{it.hint}</KeyCap>}
              </span>
            </div>
          ))}
        </div>

        <div style={{ position: 'absolute', bottom: 26, left: 26, right: 26 }}>
          <div className="ink-rule" style={{ marginBottom: 12 }} />
          <div className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.18em' }}>
            BLOCK-7 · MU GU ZHEN · v0.3
          </div>
        </div>
      </div>
    </>
  );
}

// ---------------- F · S4 "read your own heart" full immersive modal ----------------
function InnerHeart({ playerNpc, reflections, onClose }) {
  return (
    <>
      <div style={{
        position: 'absolute', inset: 0,
        background: 'rgba(26,20,16,0.78)',
        backdropFilter: 'blur(2px)'
      }} className="modalfade" />
      <div className="modalfade" style={{
        position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        width: 760, height: 540,
        display: 'flex',
        filter: 'drop-shadow(0 18px 48px rgba(0,0,0,0.6))'
      }}>
        {/* Notebook — two facing pages, parchment with center binding */}
        <div className="parchment" style={{ width: 380, position: 'relative', padding: '36px 36px 36px 44px', borderRadius: '4px 0 0 4px' }}>
          <CornerFlourish />
          <div className="serif" style={{ position: 'relative', zIndex: 1, fontSize: 13, fontStyle: 'italic', color: '#6b5840', letterSpacing: '0.04em' }}>
            左页 · 你自己的想法
          </div>
          <div className="serif" style={{ position: 'relative', zIndex: 1, fontSize: 26, fontWeight: 600, color: '#3d2f1f', marginTop: 6, letterSpacing: '0.04em' }}>
            {playerNpc.name}
          </div>
          <div className="ink-rule" style={{ margin: '16px 0 18px', position: 'relative', zIndex: 1 }} />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 18, position: 'relative', zIndex: 1 }}>
            {reflections.slice(0, 2).map((r, i) => (
              <div key={i} className="handwriting inkbleed" style={{
                fontSize: 22, lineHeight: 1.4, color: '#3d2f1f',
                fontFamily: '"Ma Shan Zheng", "Caveat", cursive',
                animationDelay: (0.2 + i * 0.4) + 's'
              }}>
                {r.text}
              </div>
            ))}
          </div>

          <div style={{ position: 'absolute', bottom: 22, left: 44, right: 28 }}>
            <div className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.18em', textTransform: 'uppercase' }}>
              · ± 今日 · 1 / 2 ·
            </div>
          </div>
        </div>

        {/* binding shadow */}
        <div style={{
          width: 8,
          background: 'linear-gradient(90deg, rgba(60,40,20,0.45), rgba(20,12,4,0.6) 50%, rgba(60,40,20,0.45))',
          boxShadow: 'inset 0 0 8px rgba(0,0,0,0.4)'
        }} />

        <div className="parchment" style={{ width: 380, position: 'relative', padding: '36px 44px 36px 36px', borderRadius: '0 4px 4px 0' }}>
          <div className="serif" style={{ position: 'relative', zIndex: 1, fontSize: 13, fontStyle: 'italic', color: '#6b5840', textAlign: 'right' }}>
            右页 · 另一种声音 · 反思 · 随笔
          </div>
          <div className="ink-rule" style={{ margin: '16px 0 18px', position: 'relative', zIndex: 1 }} />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 18, position: 'relative', zIndex: 1 }}>
            {reflections.slice(2).map((r, i) => (
              <div key={i} className="handwriting inkbleed" style={{
                fontSize: 20, lineHeight: 1.5,
                color: 'rgba(61,47,31,0.62)',
                fontFamily: '"Caveat", "Ma Shan Zheng", cursive',
                fontStyle: 'italic',
                letterSpacing: '0.02em',
                animationDelay: (0.6 + i * 0.4) + 's'
              }}>
                {r.text}
              </div>
            ))}
          </div>

          <div className="serif" style={{
            position: 'absolute', bottom: 60, right: 28, left: 36,
            fontSize: 11, fontStyle: 'italic',
            color: 'rgba(107,88,64,0.55)',
            borderTop: '1px dashed rgba(107,88,64,0.3)',
            paddingTop: 8,
            position: 'absolute',
            lineHeight: 1.5
          }}>
            字体变化预留 · 剧本可注入「导演低语 / 母亲遗笔 / 沉睡的记忆」等不同源头。
          </div>

          {/* corner ribbon — "Esc to close" hint */}
          <div className="mono" style={{
            position: 'absolute', bottom: 22, right: 28,
            fontSize: 10, color: '#6b5840', letterSpacing: '0.18em', textTransform: 'uppercase',
            display: 'flex', alignItems: 'center', gap: 6
          }}>
            <KeyCap dim>F</KeyCap><span>合上</span>
          </div>
        </div>
      </div>
    </>
  );
}

// ---------------- T · big-event log sidebar ----------------
function EventLog({ events, onClose, day }) {
  return (
    <>
      <div style={{
        position: 'absolute', inset: 0,
        background: 'rgba(26,20,16,0.30)'
      }} className="modalfade" />
      <div className="parchment modalfade" style={{
        position: 'absolute', left: 0, top: 0, bottom: 0,
        width: 360, padding: '34px 28px 28px',
        boxShadow: '12px 0 32px rgba(10,6,2,0.5), inset -1px 0 0 #6b5840',
        borderRadius: 0
      }}>
        <CornerFlourish />
        <div className="serif" style={{ fontSize: 22, fontWeight: 600, color: '#3d2f1f', letterSpacing: '0.06em', position: 'relative', zIndex: 1 }}>
          大事日志
        </div>
        <div className="mono" style={{
          fontSize: 10, color: '#6b5840', letterSpacing: '0.18em', marginTop: 4, textTransform: 'uppercase',
          position: 'relative', zIndex: 1
        }}>T · CHRONICLE</div>

        <div className="ink-rule" style={{ margin: '16px 0', position: 'relative', zIndex: 1 }} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, position: 'relative', zIndex: 1 }}>
          {events.map((e, i) => (
            <div key={i} style={{ display: 'flex', gap: 10 }}>
              <div style={{ flex: '0 0 56px' }}>
                <div className="mono" style={{ fontSize: 9, letterSpacing: '0.14em', color: '#8b4513' }}>
                  DAY {e.day}
                </div>
                <div className="mono" style={{ fontSize: 11, color: '#3d2f1f' }}>
                  {e.time}
                </div>
              </div>
              <div style={{ flex: 1, paddingLeft: 12, borderLeft: '1px solid rgba(107,88,64,0.35)' }}>
                <div className="mono" style={{ fontSize: 9, color: '#6b5840', letterSpacing: '0.14em', textTransform: 'uppercase' }}>{e.tag}</div>
                <div className="serif" style={{ fontSize: 14, color: '#3d2f1f', marginTop: 2, lineHeight: 1.4 }}>
                  {e.text}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

// ---------------- S11 · dialogue (full-screen heavy, hybrid input) ----------------
function DialogueSession({ player, npc, lines, onClose }) {
  const [input, setInput] = React.useState('');
  const [thinking, setThinking] = React.useState(false);
  const [round, setRound] = React.useState(3);
  const inputRef = React.useRef(null);

  const useChoice = (text) => { setInput(text); inputRef.current && inputRef.current.focus(); };
  const sendChoice = (text) => {
    setInput('');
    const dur = Math.max(2, text.length * 0.15);
    setThinking(true);
    setTimeout(() => { setThinking(false); setRound(r => r + 1); }, dur * 1000);
  };
  const submit = () => {
    if (!input.trim() || thinking) return;
    sendChoice(input);
  };

  return (
    <>
      <div style={{
        position: 'absolute', inset: 0,
        background: 'rgba(26,20,16,0.78)',
        backdropFilter: 'blur(1.5px)'
      }} className="modalfade" />
      <div className="modalfade" style={{ position: 'absolute', inset: 0 }}>
        {/* portraits flank the scroll */}
        <div style={{ position: 'absolute', left: 60, bottom: 360, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
          <Portrait npc={npc} size={220} />
          <div className="serif" style={{ fontSize: 18, fontWeight: 600, color: '#f4e6cf', letterSpacing: '0.06em', textShadow: '0 1px 4px rgba(0,0,0,0.7)' }}>
            {npc.name}
            {thinking && <span className="mono" style={{ fontSize: 12, color: '#c8a4d4', marginLeft: 10, letterSpacing: '0.3em' }}>· · ·</span>}
          </div>
          <div className="mono" style={{ fontSize: 10, color: 'rgba(244,230,207,0.7)', letterSpacing: '0.16em', textTransform: 'uppercase' }}>{npc.role}</div>
        </div>
        <div style={{ position: 'absolute', right: 60, bottom: 360, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
          <Portrait npc={player} size={220} />
          <div className="serif" style={{ fontSize: 18, fontWeight: 600, color: '#f4e6cf', letterSpacing: '0.06em', textShadow: '0 1px 4px rgba(0,0,0,0.7)' }}>
            {player.name}
          </div>
          <div className="mono" style={{ fontSize: 10, color: 'rgba(244,230,207,0.7)', letterSpacing: '0.16em', textTransform: 'uppercase' }}>你</div>
        </div>

        {/* Long parchment dialog scroll */}
        <div className="parchment" style={{
          position: 'absolute', left: 60, right: 60, bottom: 40,
          height: 320,
          padding: '20px 28px',
          borderRadius: 4,
          display: 'flex', flexDirection: 'column'
        }}>
          <CornerFlourish />
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, position: 'relative', zIndex: 1 }}>
            <span className="serif" style={{ fontSize: 18, fontWeight: 600, color: '#3d2f1f', letterSpacing: '0.04em' }}>
              {npc.name}
            </span>
            <span className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.18em', textTransform: 'uppercase' }}>
              {npc.role}
            </span>
            <span style={{ flex: 1 }} />
            <span className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.14em' }}>
              对话 · 第 {round} 轮
            </span>
          </div>
          <div className="ink-rule" style={{ margin: '10px 0 12px', position: 'relative', zIndex: 1 }} />
          <div className="serif inkbleed" style={{
            position: 'relative', zIndex: 1,
            fontSize: 19, lineHeight: 1.5, color: '#3d2f1f',
            minHeight: 50,
          }}>
            {thinking
              ? <span style={{ color: '#6b5840', fontStyle: 'italic' }}>{npc.name} 在斟酌…</span>
              : lines.current}
          </div>

          <div className="ink-rule" style={{ margin: '12px 0 10px', position: 'relative', zIndex: 1 }} />

          {/* LLM choices — each has [→ send] and [✎ edit] affordances */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, position: 'relative', zIndex: 1 }}>
            {lines.choices.map((c, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '4px 8px',
                borderRadius: 3,
                background: i === 0 ? 'rgba(139,69,19,0.06)' : 'transparent',
                border: '1px solid ' + (i === 0 ? 'rgba(139,69,19,0.25)' : 'rgba(107,88,64,0.18)')
              }}>
                <KeyCap dim>{i + 1}</KeyCap>
                <span className="serif" style={{
                  flex: 1,
                  fontSize: 15, fontStyle: 'italic',
                  color: i === 0 ? '#8b4513' : '#3d2f1f',
                }}>{c}</span>
                <button onClick={() => useChoice(c)} title="复制到输入框编辑" style={iconBtn}>✎</button>
                <button onClick={() => sendChoice(c)} title="直接发送原候选" style={iconBtn}>→</button>
              </div>
            ))}
          </div>

          {/* Hybrid input row — bottom 1/3 */}
          <div style={{
            marginTop: 12,
            display: 'flex', gap: 8,
            position: 'relative', zIndex: 1,
            paddingTop: 10,
            borderTop: '1px dashed rgba(107,88,64,0.45)'
          }}>
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') submit(); }}
              placeholder={thinking ? `${npc.name} 在斟酌中…` : '或在这里写你自己的话…'}
              disabled={thinking}
              className="serif"
              style={{
                flex: 1,
                background: 'rgba(232,220,196,0.7)',
                border: '1px solid #6b5840',
                borderRadius: 3,
                padding: '8px 12px',
                fontSize: 16,
                color: '#3d2f1f',
                fontFamily: '"Cormorant Garamond","Noto Serif SC",serif',
                outline: 'none',
              }}
            />
            <button onClick={submit} disabled={thinking || !input.trim()} className="serif" style={{
              background: thinking ? 'rgba(107,88,64,0.2)' : '#8b4513',
              color: thinking ? '#6b5840' : '#f4e6cf',
              border: '1px solid #6b5840',
              borderRadius: 3,
              padding: '8px 18px',
              fontSize: 15, fontWeight: 600,
              letterSpacing: '0.06em',
              cursor: thinking ? 'not-allowed' : 'pointer',
              fontFamily: '"Cormorant Garamond","Noto Serif SC",serif',
            }}>
              发送
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8, position: 'relative', zIndex: 1 }}>
            <div className="mono" style={{ fontSize: 9, color: '#6b5840', letterSpacing: '0.14em' }}>
              点候选 ✎ = 复制到输入框可编辑 · 点 → = 原样发送 · 发送后按字数读秒(最少 2 秒)
            </div>
            <div className="mono" style={{ fontSize: 9, color: '#6b5840', letterSpacing: '0.18em', display: 'flex', gap: 6, alignItems: 'center' }}>
              <KeyCap dim>Esc</KeyCap><span>离开对话</span>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

const iconBtn = {
  background: 'transparent',
  border: '1px solid rgba(107,88,64,0.45)',
  borderRadius: 2,
  color: '#6b5840',
  width: 22, height: 22,
  padding: 0,
  cursor: 'pointer',
  fontFamily: 'serif', fontSize: 13,
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center'
};

// ---------------- S5 · relationship network (full-screen heavy) ----------------
// Three observation states for healer suspicion:
//   0 → 无标记
//   1-2 → 节点边缘灰色虚线圈("觉得哪里不对")
//   3+ → 紫色实线圈("已确认治愈者")
function RelationshipNetwork({ npcs, player, onClose }) {
  const cx = 480, cy = 280, r = 200;
  const n = npcs.length;
  const [hover, setHover] = React.useState(null);

  // Per-NPC suspicion scores (would be system-driven in real game)
  const sus = {
    1: 3,   // 林秋 — confirmed (dream particles seen + dialogue mention + heard from suzhi)
    2: 2,   // 阿杏 — suspicion (heard 2 sources)
    12: 1,  // 白嬤 — first inkling
    7: 1,   // 苏拂 — first inkling (heard about her husband)
  };
  // Observation logs (hover tooltip)
  const observe = {
    1: { close: 2, heard: 1, talked: 3 },
    2: { close: 0, heard: 2, talked: 1 },
    12: { close: 0, heard: 1, talked: 0 },
    7: { close: 1, heard: 0, talked: 1 },
  };

  return (
    <>
      <div style={{
        position: 'absolute', inset: 0,
        background: 'rgba(26,20,16,0.78)', backdropFilter: 'blur(1.5px)'
      }} className="modalfade" />
      <div className="parchment modalfade" style={{
        position: 'absolute', left: 80, top: 60, right: 80, bottom: 60,
        padding: '28px 36px',
        borderRadius: 4
      }}>
        <CornerFlourish />
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', position: 'relative', zIndex: 1 }}>
          <div>
            <div className="serif" style={{ fontSize: 26, fontWeight: 600, color: '#3d2f1f' }}>关系网</div>
            <div className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.18em', textTransform: 'uppercase', marginTop: 2 }}>
              R · 你所感知的连结
            </div>
          </div>
          <div className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.18em' }}>
            DAY 3 · 11 人 · 未知关系 4
          </div>
        </div>
        <div className="ink-rule" style={{ margin: '14px 0', position: 'relative', zIndex: 1 }} />

        <svg viewBox="0 0 960 560" style={{ width: '100%', height: 460, position: 'relative', zIndex: 1 }}>
          {/* relationship arcs */}
          {npcs.map((a, i) => {
            const ax = cx + Math.cos((i / n) * Math.PI * 2 - Math.PI / 2) * r;
            const ay = cy + Math.sin((i / n) * Math.PI * 2 - Math.PI / 2) * r;
            return npcs.map((b, j) => {
              if (j <= i) return null;
              const known = [[0,1], [0,9], [5,7], [10,3], [5,4], [4,2]];
              const isKnown = known.some(p => (p[0] === i && p[1] === j) || (p[0] === j && p[1] === i));
              if (!isKnown) return null;
              const bx = cx + Math.cos((j / n) * Math.PI * 2 - Math.PI / 2) * r;
              const by = cy + Math.sin((j / n) * Math.PI * 2 - Math.PI / 2) * r;
              return <line key={i+'-'+j} x1={ax} y1={ay} x2={bx} y2={by} stroke="#6b5840" strokeWidth="1.2" opacity="0.5" strokeDasharray={(i+j) % 3 === 0 ? "3 3" : ""} />;
            });
          })}
          {/* nodes */}
          {npcs.map((nP, i) => {
            const ax = cx + Math.cos((i / n) * Math.PI * 2 - Math.PI / 2) * r;
            const ay = cy + Math.sin((i / n) * Math.PI * 2 - Math.PI / 2) * r;
            const isPlayer = player && nP.id === player.id;
            const score = sus[nP.id] || 0;
            // ring state from suspicion
            const ringState = score >= 3 ? 'confirmed' : score >= 1 ? 'suspect' : 'none';
            return (
              <g key={nP.id} style={{ cursor: 'pointer' }}
                 onMouseEnter={() => setHover({ npc: nP, x: ax, y: ay, score, ringState })}
                 onMouseLeave={() => setHover(null)}>
                {/* outer suspicion ring */}
                {ringState === 'suspect' && (
                  <circle cx={ax} cy={ay} r={24} fill="none" stroke="#a09080" strokeWidth="1.3" strokeDasharray="3 3" opacity="0.85" />
                )}
                {ringState === 'confirmed' && (
                  <circle cx={ax} cy={ay} r={24} fill="none" stroke="#7a5a96" strokeWidth="2" />
                )}
                {/* node */}
                <circle cx={ax} cy={ay} r={isPlayer ? 22 : 18} fill={nP.color}
                  stroke={isPlayer ? '#8b4513' : '#6b5840'}
                  strokeWidth={isPlayer ? 3 : 1} />
                <text x={ax} y={ay + 40} textAnchor="middle"
                      fill="#3d2f1f" fontFamily="Cormorant Garamond, Noto Serif SC, serif"
                      fontSize="14">{nP.name}</text>
                {isPlayer && (
                  <text x={ax} y={ay + 4} textAnchor="middle"
                        fill="#fff" fontFamily="IBM Plex Mono, monospace"
                        fontSize="9" letterSpacing="0.1em">YOU</text>
                )}
              </g>
            );
          })}

          {/* hover tooltip */}
          {hover && observe[hover.npc.id] && (
            <g style={{ pointerEvents: 'none' }}>
              <rect x={hover.x + 30} y={hover.y - 50} width="220" height="92"
                    fill="#e8dcc4" stroke="#6b5840" strokeWidth="1" rx="3" />
              <text x={hover.x + 42} y={hover.y - 30} fill="#8b4513"
                    fontFamily="IBM Plex Mono, monospace" fontSize="9"
                    letterSpacing="2">观察记录 · OBSERVATION</text>
              <line x1={hover.x + 42} y1={hover.y - 22} x2={hover.x + 240} y2={hover.y - 22} stroke="#6b5840" opacity="0.4" />
              <text x={hover.x + 42} y={hover.y - 6} fill="#3d2f1f"
                    fontFamily="Cormorant Garamond, Noto Serif SC, serif" fontSize="13">
                近距离观察 {observe[hover.npc.id].close} 次
              </text>
              <text x={hover.x + 42} y={hover.y + 10} fill="#3d2f1f"
                    fontFamily="Cormorant Garamond, Noto Serif SC, serif" fontSize="13">
                听旁人提起 {observe[hover.npc.id].heard} 次
              </text>
              <text x={hover.x + 42} y={hover.y + 26} fill="#3d2f1f"
                    fontFamily="Cormorant Garamond, Noto Serif SC, serif" fontSize="13">
                直接对话 {observe[hover.npc.id].talked} 次
              </text>
            </g>
          )}
        </svg>

        <div style={{ display: 'flex', gap: 18, position: 'relative', zIndex: 1, marginTop: 6, flexWrap: 'wrap' }}>
          <Legend swatch="#8b4513" label="你" border={3} />
          <Legend swatch="#c8b8a0" label="关系 · 已知" />
          <Legend swatch="#c8b8a0" dashed label="关系 · 听说" />
          <span style={{ display: 'inline-block', width: 1, background: 'rgba(107,88,64,0.4)' }} />
          <Legend swatch="#c8b8a0" label='0 分 · 无标记(未注意)' />
          <Legend swatch="#c8b8a0" outerDashed outerColor="#a09080" label='1-2 分 · 灰虚 · 觉得哪里不对' />
          <Legend swatch="#c8b8a0" outerSolid outerColor="#7a5a96" label='3+ 分 · 紫实 · 已确认治愈者' />
        </div>
      </div>
    </>
  );
}
function Legend({ swatch, label, dashed, border = 1, ring, outerDashed, outerSolid, outerColor }) {
  if (outerDashed || outerSolid) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{
          display: 'inline-block', width: 20, height: 20, borderRadius: '50%',
          border: outerSolid ? `2px solid ${outerColor}` : `1.3px dashed ${outerColor}`,
          padding: 2,
          boxSizing: 'border-box',
          position: 'relative'
        }}>
          <span style={{
            display: 'block', width: 12, height: 12, borderRadius: '50%',
            background: swatch, border: '1px solid #6b5840'
          }} />
        </span>
        <span className="serif" style={{ fontSize: 13, color: '#3d2f1f' }}>{label}</span>
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <span style={{
        display: 'inline-block', width: 14, height: 14, borderRadius: '50%',
        background: swatch, border: `${border}px solid ${ring || '#6b5840'}`,
        ...(dashed ? { background: `repeating-linear-gradient(45deg, ${swatch} 0 3px, transparent 3px 6px)` } : {})
      }} />
      <span className="serif" style={{ fontSize: 13, color: '#3d2f1f' }}>{label}</span>
    </div>
  );
}

// ---------------- A small ink-flourish corner used in panels ----------------
function CornerFlourish() {
  return (
    <svg width="80" height="80" viewBox="0 0 80 80" style={{
      position: 'absolute', top: 6, right: 6, opacity: 0.18, pointerEvents: 'none'
    }}>
      <path d="M70 10 Q 40 12 24 28 Q 10 44 12 70"
            stroke="#3d2f1f" strokeWidth="1.2" fill="none" />
      <circle cx="70" cy="10" r="2" fill="#3d2f1f" />
      <path d="M40 18 Q 38 24 32 28" stroke="#3d2f1f" strokeWidth="0.8" fill="none" opacity="0.7" />
      <path d="M52 12 Q 50 18 44 22" stroke="#3d2f1f" strokeWidth="0.8" fill="none" opacity="0.6" />
    </svg>
  );
}

const cornerBtn = {
  background: 'transparent',
  border: '1px solid rgba(107,88,64,0.45)',
  borderRadius: 3,
  color: '#6b5840',
  fontSize: 9,
  letterSpacing: '0.14em',
  textTransform: 'uppercase',
  padding: '3px 8px',
  cursor: 'pointer',
  fontFamily: 'IBM Plex Mono, monospace'
};

window.LocationCard = LocationCard;
window.SystemMenu = SystemMenu;
window.InnerHeart = InnerHeart;
window.EventLog = EventLog;
window.DialogueSession = DialogueSession;
window.RelationshipNetwork = RelationshipNetwork;
window.CornerFlourish = CornerFlourish;
