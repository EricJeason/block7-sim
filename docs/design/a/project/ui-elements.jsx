// ui-elements.jsx — small HUD components.
// All chrome here is parchment + oak ink — no flat dark panels.

// ---------------- Wood plank clock ----------------
// 240x52 wood plank with a time-of-day icon and "DAY 3 · 15:52".
// Hangs from the top edge (top: -4px slot in screen).
// Time-of-day icon variants:
//   morning: rising sun (low arc)
//   noon:    full sun
//   dusk:    half sun on horizon
//   night:   crescent moon
function ClockIcon({ phase }) {
  const c = {
    morning: '#e8a04a',
    noon:    '#f4c054',
    dusk:    '#d8804a',
    night:   '#e8e0c4',
  }[phase];
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" shapeRendering="crispEdges" style={{ marginRight: 8 }}>
      {phase === 'morning' && (
        <>
          <rect x="7" y="6" width="4" height="4" fill={c} />
          <rect x="6" y="7" width="6" height="2" fill={c} />
          <rect x="8" y="2" width="2" height="2" fill={c} />
          <rect x="2" y="8" width="2" height="2" fill={c} />
          <rect x="14" y="8" width="2" height="2" fill={c} />
          <rect x="3" y="3" width="2" height="2" fill={c} opacity="0.7" />
          <rect x="13" y="3" width="2" height="2" fill={c} opacity="0.7" />
          {/* horizon */}
          <rect x="0" y="13" width="18" height="1" fill="#6b5840" opacity="0.6" />
        </>
      )}
      {phase === 'noon' && (
        <>
          <rect x="6" y="6" width="6" height="6" fill={c} />
          <rect x="5" y="7" width="8" height="4" fill={c} />
          <rect x="7" y="5" width="4" height="8" fill={c} />
          <rect x="8" y="1" width="2" height="2" fill={c} />
          <rect x="8" y="15" width="2" height="2" fill={c} />
          <rect x="1" y="8" width="2" height="2" fill={c} />
          <rect x="15" y="8" width="2" height="2" fill={c} />
          <rect x="3" y="3" width="2" height="2" fill={c} />
          <rect x="13" y="3" width="2" height="2" fill={c} />
          <rect x="3" y="13" width="2" height="2" fill={c} />
          <rect x="13" y="13" width="2" height="2" fill={c} />
        </>
      )}
      {phase === 'dusk' && (
        <>
          <rect x="6" y="8" width="6" height="4" fill={c} />
          <rect x="7" y="6" width="4" height="4" fill={c} />
          <rect x="2" y="9" width="2" height="2" fill={c} opacity="0.7" />
          <rect x="14" y="9" width="2" height="2" fill={c} opacity="0.7" />
          <rect x="0" y="12" width="18" height="1" fill="#6b5840" />
          <rect x="0" y="13" width="18" height="1" fill="#6b5840" opacity="0.5" />
        </>
      )}
      {phase === 'night' && (
        <>
          <rect x="5" y="4" width="7" height="10" fill={c} />
          <rect x="6" y="3" width="5" height="1" fill={c} />
          <rect x="6" y="14" width="5" height="1" fill={c} />
          <rect x="7" y="5" width="6" height="8" fill="#3d2f1f" />
          <rect x="14" y="3" width="1" height="1" fill={c} opacity="0.7" />
          <rect x="2" y="11" width="1" height="1" fill={c} opacity="0.7" />
          <rect x="15" y="8" width="1" height="1" fill={c} opacity="0.5" />
        </>
      )}
    </svg>
  );
}

function phaseFromHour(h) {
  if (h >= 6 && h < 11) return 'morning';
  if (h >= 11 && h < 17) return 'noon';
  if (h >= 17 && h < 20) return 'dusk';
  return 'night';
}

function WoodClock({ day = 3, hour = 15, minute = 52, cracked = false }) {
  const phase = phaseFromHour(hour);
  const pad = n => String(n).padStart(2, '0');
  return (
    <div className="wood" style={{
      position: 'relative',
      width: 240, height: 52,
      borderRadius: '0 0 6px 6px',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '0 18px',
      fontFamily: '"Cormorant Garamond","Noto Serif SC",serif',
      fontWeight: 600,
      fontSize: 21,
      letterSpacing: '0.08em',
      color: '#3d2f1f',
      textShadow: '0 1px 0 rgba(255,235,200,0.5)'
    }}>
      {/* nail heads */}
      <span style={{ position: 'absolute', left: 8, top: 8, width: 4, height: 4, borderRadius: '50%', background: '#3a2418', boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.2)' }} />
      <span style={{ position: 'absolute', right: 8, top: 8, width: 4, height: 4, borderRadius: '50%', background: '#3a2418', boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.2)' }} />
      <span style={{ position: 'absolute', left: 8, bottom: 8, width: 4, height: 4, borderRadius: '50%', background: '#3a2418' }} />
      <span style={{ position: 'absolute', right: 8, bottom: 8, width: 4, height: 4, borderRadius: '50%', background: '#3a2418' }} />

      {/* subtle hairline crack — appears as days advance (atmosphere) */}
      {cracked && (
        <svg style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} width="240" height="52">
          <path d="M 80 0 L 96 14 L 90 26 L 110 38 L 102 52" stroke="rgba(40,20,8,0.5)" strokeWidth="0.6" fill="none" />
          <path d="M 96 14 L 88 20" stroke="rgba(40,20,8,0.4)" strokeWidth="0.5" fill="none" />
        </svg>
      )}

      <ClockIcon phase={phase} />
      <span>DAY {day} · {pad(hour)}:{pad(minute)}</span>
    </div>
  );
}

// ---------------- E key bubble menu ----------------
// Appears above the targeted NPC. Parchment with ink border, downward tail.
function BubbleMenu({ npc, options, selected = 0 }) {
  return (
    <div style={{ position: 'relative', filter: 'drop-shadow(0 6px 14px rgba(20,10,4,0.45))' }}>
      {/* npc name above menu */}
      <div className="serif" style={{
        textAlign: 'center', color: '#3d2f1f',
        fontSize: 14, fontWeight: 600, letterSpacing: '0.04em',
        marginBottom: 4,
        textShadow: '0 1px 0 rgba(245,235,200,0.7)'
      }}>{npc.name}</div>

      <div className="parchment" style={{
        position: 'relative',
        borderRadius: 5,
        padding: '6px 4px',
        minWidth: 124,
      }}>
        {options.map((opt, i) => (
          <div key={i} className="serif" style={{
            position: 'relative', zIndex: 1,
            padding: '4px 14px 4px 22px',
            fontSize: 15,
            color: i === selected ? '#8b4513' : '#3d2f1f',
            background: i === selected ? 'rgba(139,69,19,0.10)' : 'transparent',
            borderRadius: 3,
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between'
          }}>
            {i === selected && (
              <span style={{
                position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)',
                width: 0, height: 0,
                borderLeft: '5px solid #8b4513',
                borderTop: '4px solid transparent',
                borderBottom: '4px solid transparent'
              }} />
            )}
            <span>{opt.label}</span>
            {opt.cost && (
              <span className="mono" style={{
                fontSize: 10, color: '#8b4513', marginLeft: 8, letterSpacing: '0.04em'
              }}>{opt.cost}</span>
            )}
          </div>
        ))}
      </div>

      {/* tail */}
      <svg width="20" height="14" viewBox="0 0 20 14" style={{
        position: 'absolute', left: '50%', bottom: -12, transform: 'translateX(-50%)'
      }}>
        <polygon points="0,0 20,0 10,12" fill="#e3d3b3" />
        <polyline points="0,0 10,12 20,0" stroke="#6b5840" strokeWidth="1" fill="none" />
      </svg>
    </div>
  );
}

// ---------------- Hover whisper above NPC ----------------
// Per v2.1 brief: format is "NPC名 · action描述" (with name).
// Optionally render encumbrance chip next to it.
function HoverWhisper({ name, text, load, max }) {
  return (
    <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
      <div className="serif" style={{
        fontSize: 13,
        color: 'rgba(40,30,20,0.78)',
        whiteSpace: 'nowrap',
        textShadow: '0 1px 2px rgba(245,235,200,0.65)',
        letterSpacing: '0.02em',
        background: 'rgba(232,220,196,0.78)',
        border: '1px solid rgba(107,88,64,0.45)',
        borderRadius: 2,
        padding: '1px 8px'
      }}>
        <span style={{ fontWeight: 600, color: '#3d2f1f', marginRight: 4 }}>{name}</span>
        <span style={{ color: 'rgba(107,88,64,0.7)' }}>·</span>
        <span style={{ fontStyle: 'italic', marginLeft: 4 }}>{text}</span>
      </div>
      {typeof load === 'number' && (
        <EncumbranceChip compact load={load} max={max} />
      )}
    </div>
  );
}

// ---------------- Location label (bottom-left) ----------------
function LocationLabel({ name, en, count }) {
  return (
    <div style={{
      color: 'rgba(50,38,24,0.92)',
      textShadow: '0 1px 2px rgba(245,235,200,0.55), 0 0 8px rgba(245,235,200,0.45)'
    }}>
      <div className="serif" style={{ fontSize: 30, fontWeight: 600, letterSpacing: '0.04em', lineHeight: 1 }}>
        {name}
      </div>
      <div className="mono" style={{ fontSize: 11, color: 'rgba(60,46,28,0.6)', marginTop: 4, letterSpacing: '0.16em', textTransform: 'uppercase' }}>
        {en} · {count} HERE
      </div>
    </div>
  );
}

// ---------------- Key hint (bottom-right) ----------------
function KeyHints({ hints }) {
  return (
    <div className="mono" style={{
      display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4,
      fontSize: 11, color: 'rgba(40,30,20,0.7)', letterSpacing: '0.06em',
      textShadow: '0 1px 1px rgba(245,235,200,0.5)'
    }}>
      {hints.map((h, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <KeyCap>{h.key}</KeyCap>
          <span style={{ fontSize: 11, letterSpacing: '0.02em' }}>{h.label}</span>
        </div>
      ))}
    </div>
  );
}
function KeyCap({ children, dim }) {
  return (
    <span className="mono" style={{
      display: 'inline-block',
      minWidth: 18,
      padding: '1px 5px',
      borderRadius: 3,
      background: 'rgba(232,220,196,0.85)',
      color: '#3d2f1f',
      border: '1px solid rgba(107,88,64,0.55)',
      boxShadow: '0 1px 0 rgba(107,88,64,0.4)',
      fontSize: 10, fontWeight: 600,
      letterSpacing: '0.04em', textAlign: 'center',
      opacity: dim ? 0.6 : 1
    }}>{children}</span>
  );
}

// ---------------- Name tag (floats above NPC when within range) ----------------
function NameTag({ npc, hint, showHealerHint }) {
  const isHealer = npc.healer && showHealerHint;
  return (
    <div style={{
      position: 'relative',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      filter: isHealer ? 'drop-shadow(0 0 4px rgba(150,110,180,0.55))' : 'none',
    }}>
      {hint && (
        <div style={{ marginBottom: 4 }}>
          <HoverWhisper text={hint} />
        </div>
      )}
      <div className="serif" style={{
        fontSize: 12,
        fontWeight: 500,
        padding: '1px 8px',
        color: '#3d2f1f',
        background: 'rgba(232,220,196,0.88)',
        border: '1px solid ' + (isHealer ? 'rgba(122,90,150,0.55)' : 'rgba(107,88,64,0.55)'),
        borderRadius: 2,
        letterSpacing: '0.03em',
        boxShadow: isHealer ? 'inset 0 0 8px rgba(160,120,190,0.18)' : '0 1px 0 rgba(107,88,64,0.18)'
      }}>{npc.name}</div>
    </div>
  );
}

window.WoodClock = WoodClock;
window.BubbleMenu = BubbleMenu;
window.HoverWhisper = HoverWhisper;
window.LocationLabel = LocationLabel;
window.KeyHints = KeyHints;
window.KeyCap = KeyCap;
window.NameTag = NameTag;
