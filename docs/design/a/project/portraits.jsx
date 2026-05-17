// portraits.jsx — 256×256 bust portraits (code placeholders).
// These are EXPLICITLY placeholders until art is provided. They use the NPC's
// palette + an anime-style bust silhouette (head/shoulders/garment) at higher
// fidelity than the 14×22 walk sprite, so the design system can show what the
// portrait slot looks like inside dialogue / character panel / inventory.
//
// Variants: "normal" / "infected" / "healer-marked"
// - infected: red sclera, pale skin, ragged collar, desaturated palette
// - healer-marked: subtle purple aura, no visible body change

function Portrait({ npc, variant = 'normal', size = 256 }) {
  const palette = makePalette(npc, variant);
  return (
    <div style={{
      position: 'relative',
      width: size, height: size,
      borderRadius: 4,
      overflow: 'hidden',
      background: palette.bg,
      boxShadow: variant === 'healer-marked'
        ? '0 0 18px rgba(122,90,150,0.4) inset, 0 0 0 1px rgba(122,90,150,0.45)'
        : 'inset 0 0 0 1px rgba(107,88,64,0.55)',
    }}>
      <BustSVG npc={npc} palette={palette} variant={variant} size={size} />

      {/* "PORTRAIT · ART TBD" watermark in corner */}
      <div className="mono" style={{
        position: 'absolute', left: 6, bottom: 6,
        fontSize: 9, color: 'rgba(245,235,200,0.55)',
        letterSpacing: '0.18em',
        background: 'rgba(20,12,4,0.45)',
        padding: '2px 6px', borderRadius: 2,
      }}>PORTRAIT · 256 · 占位</div>

      {variant === 'healer-marked' && (
        <div style={{
          position: 'absolute', inset: 0, pointerEvents: 'none',
          background: 'radial-gradient(circle at 50% 30%, rgba(122,90,150,0.15), transparent 65%)'
        }} />
      )}
    </div>
  );
}

function makePalette(npc, variant) {
  const desaturate = (hex) => {
    // pull toward gray for infected
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    const avg = (r+g+b)/3;
    const mix = (c) => Math.round(c * 0.55 + avg * 0.45);
    return `#${mix(r).toString(16).padStart(2,'0')}${mix(g).toString(16).padStart(2,'0')}${mix(b).toString(16).padStart(2,'0')}`;
  };
  const dim = (hex, k=0.85) => {
    const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
    return `rgb(${Math.round(r*k)},${Math.round(g*k)},${Math.round(b*k)})`;
  };
  if (variant === 'infected') {
    return {
      bg: 'linear-gradient(180deg, #6e6660 0%, #3a3530 100%)',
      skin: '#d8c4a8',  // paler
      hair: dim(npc.hair, 0.85),
      shirt: desaturate(npc.color),
      accent: desaturate(npc.accent),
      eyeWhite: '#e8b8a8',  // pinkish sclera
      iris: '#b8302a',       // red iris
      mouth: '#5a2018',
      shadow: 'rgba(80,30,30,0.5)',
      tear: '#3a1818',
    };
  }
  return {
    bg: 'linear-gradient(180deg, #5a4a36 0%, #2a1f14 100%)',
    skin: npc.skin,
    hair: npc.hair,
    shirt: npc.color,
    accent: npc.accent,
    eyeWhite: '#f4e6cf',
    iris: '#3a2a18',
    mouth: '#6b3a20',
    shadow: 'rgba(0,0,0,0.4)',
    tear: null,
  };
}

function BustSVG({ npc, palette, variant, size }) {
  // Coordinate system: 256×256. Bust occupies center.
  // Generic anime bust silhouette (placeholder), tinted by npc palette.
  return (
    <svg viewBox="0 0 256 256" width={size} height={size} style={{ display: 'block' }}>
      {/* shoulders / garment */}
      <path d="M 18 256 Q 32 180 80 168 Q 100 162 128 162 Q 156 162 176 168 Q 224 180 238 256 Z"
            fill={palette.shirt} />
      {/* collar accent */}
      <path d="M 80 168 L 128 200 L 176 168 L 176 178 L 128 210 L 80 178 Z"
            fill={palette.accent} opacity="0.85" />
      {/* collar trim ragged for infected */}
      {variant === 'infected' && (
        <g opacity="0.85">
          <path d="M 80 178 L 86 182 L 92 176 L 100 184 L 110 176 L 118 184 L 128 178 L 138 184 L 148 176 L 158 184 L 166 176 L 176 182"
                stroke={palette.shadow} strokeWidth="2" fill="none" />
        </g>
      )}

      {/* neck */}
      <path d="M 116 152 L 116 172 L 140 172 L 140 152 Z" fill={palette.skin} />
      <path d="M 116 168 Q 128 174 140 168 L 140 172 L 116 172 Z" fill={palette.shadow} opacity="0.35" />

      {/* head — slight oval, top a bit narrower */}
      <ellipse cx="128" cy="106" rx="44" ry="52" fill={palette.skin} />
      {/* jaw shadow */}
      <path d="M 90 130 Q 128 168 166 130 L 166 138 Q 128 174 90 138 Z" fill={palette.shadow} opacity="0.18" />

      {/* hair — back */}
      <path d="M 78 92 Q 76 56 110 44 Q 128 38 146 44 Q 180 56 178 92 Q 184 118 178 138 L 168 138 Q 174 104 168 84 Q 158 68 128 64 Q 98 68 88 84 Q 82 104 88 138 L 78 138 Q 72 118 78 92 Z"
            fill={palette.hair} />
      {/* fringe */}
      <path d={fringeShape(npc.id)} fill={palette.hair} />

      {/* eyes — anime-large with white sclera + colored iris */}
      <g>
        {/* left */}
        <ellipse cx="108" cy="116" rx="9" ry="6" fill={palette.eyeWhite} />
        <ellipse cx="108" cy="116" rx="6" ry="5.5" fill={palette.iris} />
        <ellipse cx="108" cy="115" rx="2" ry="2.5" fill="#0a0606" />
        <ellipse cx="106" cy="113" rx="1.5" ry="1.5" fill="#fff" opacity="0.95" />
        {/* right */}
        <ellipse cx="148" cy="116" rx="9" ry="6" fill={palette.eyeWhite} />
        <ellipse cx="148" cy="116" rx="6" ry="5.5" fill={palette.iris} />
        <ellipse cx="148" cy="115" rx="2" ry="2.5" fill="#0a0606" />
        <ellipse cx="146" cy="113" rx="1.5" ry="1.5" fill="#fff" opacity="0.95" />
        {/* eyebrows */}
        <path d="M 99 107 Q 108 104 117 107" stroke={palette.hair} strokeWidth="2.5" fill="none" strokeLinecap="round" />
        <path d="M 139 107 Q 148 104 157 107" stroke={palette.hair} strokeWidth="2.5" fill="none" strokeLinecap="round" />
        {/* dark circles when infected */}
        {variant === 'infected' && (
          <>
            <path d="M 100 123 Q 108 127 116 123" stroke="#5a2828" strokeWidth="1.5" fill="none" opacity="0.55" />
            <path d="M 140 123 Q 148 127 156 123" stroke="#5a2828" strokeWidth="1.5" fill="none" opacity="0.55" />
          </>
        )}
      </g>

      {/* nose hint */}
      <path d="M 128 124 L 126 134 L 130 134 Z" fill={palette.shadow} opacity="0.25" />
      {/* mouth */}
      <path d="M 122 144 Q 128 146 134 144" stroke={palette.mouth} strokeWidth="2" fill="none" strokeLinecap="round" />

      {/* role-specific accessory glyph */}
      {npc.id === 1 && <HerbBadge x={186} y={188} c={palette.accent} />}
      {npc.id === 6 && <SpearBadge x={186} y={188} c={palette.accent} />}
      {npc.id === 4 && <BookBadge x={186} y={188} c={palette.accent} />}
      {npc.id === 5 && <SealBadge x={186} y={188} c={palette.accent} />}
    </svg>
  );
}

// Different fringe shapes per NPC for some variety
function fringeShape(id) {
  switch (id % 4) {
    case 0: return 'M 88 84 Q 102 76 116 80 L 116 96 Q 100 86 88 96 Z M 140 80 Q 154 76 168 84 L 168 96 Q 156 86 140 96 Z';
    case 1: return 'M 86 82 Q 120 70 168 86 L 164 100 Q 124 78 88 102 Z';
    case 2: return 'M 92 88 Q 128 60 164 88 L 160 104 Q 128 80 96 104 Z';
    case 3: return 'M 86 80 Q 110 70 128 82 Q 146 70 170 80 L 168 96 Q 148 86 128 96 Q 108 86 88 96 Z';
  }
}

function HerbBadge({ x, y, c }) {
  return (
    <g>
      <circle cx={x} cy={y} r="14" fill="#e8dcc4" stroke="#6b5840" strokeWidth="1.5" />
      <path d={`M ${x} ${y-7} Q ${x+5} ${y} ${x} ${y+7} Q ${x-5} ${y} ${x} ${y-7} Z`} fill="#4a6b3a" />
      <path d={`M ${x} ${y-7} L ${x} ${y+7}`} stroke="#3a4a2a" strokeWidth="1" />
    </g>
  );
}
function SpearBadge({ x, y, c }) {
  return (
    <g>
      <circle cx={x} cy={y} r="14" fill="#e8dcc4" stroke="#6b5840" strokeWidth="1.5" />
      <path d={`M ${x-7} ${y+5} L ${x+5} ${y-7} L ${x+7} ${y-5} L ${x-5} ${y+7} Z`} fill="#4a4a5a" />
      <path d={`M ${x+5} ${y-7} L ${x+7} ${y-5} L ${x+3} ${y-2} L ${x+1} ${y-4} Z`} fill="#c87a3a" />
    </g>
  );
}
function BookBadge({ x, y, c }) {
  return (
    <g>
      <circle cx={x} cy={y} r="14" fill="#e8dcc4" stroke="#6b5840" strokeWidth="1.5" />
      <rect x={x-6} y={y-6} width="12" height="11" fill="#5a6fa0" />
      <rect x={x-6} y={y-6} width="12" height="2" fill="#3a4f80" />
      <line x1={x} y1={y-4} x2={x} y2={y+4} stroke="#3a4f80" strokeWidth="1" />
    </g>
  );
}
function SealBadge({ x, y, c }) {
  return (
    <g>
      <circle cx={x} cy={y} r="14" fill="#e8dcc4" stroke="#6b5840" strokeWidth="1.5" />
      <circle cx={x} cy={y} r="7" fill="#8b4513" />
      <text x={x} y={y+3} textAnchor="middle" fill="#f4e6cf" fontFamily="serif" fontSize="9">长</text>
    </g>
  );
}

// Encumbrance chip — used both inside character/inventory panels and floated
// near NPCs in S3 (lighter version).
function EncumbranceChip({ load, max, compact, color }) {
  const pct = Math.min(1, load / max);
  const level = pct < 0.33 ? '轻' : pct < 0.66 ? '中' : pct < 1 ? '重' : '满';
  const c = pct >= 1 ? '#8b4513' : pct >= 0.66 ? '#a06a3a' : '#6b5840';
  if (compact) {
    return (
      <div title={`负重 ${load}/${max}`} style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        background: 'rgba(232,220,196,0.85)',
        border: '1px solid rgba(107,88,64,0.55)',
        borderRadius: 2,
        padding: '0 4px',
        fontFamily: '"IBM Plex Mono", monospace',
        fontSize: 9,
        color: c,
        letterSpacing: '0.06em',
      }}>
        <svg width="9" height="9" viewBox="0 0 9 9">
          <path d="M2 2 L7 2 L8 7 L1 7 Z" fill="none" stroke={c} strokeWidth="1" />
          <path d="M3.5 2 Q4.5 0.5 5.5 2" stroke={c} strokeWidth="0.8" fill="none" />
        </svg>
        {level}
      </div>
    );
  }
  return (
    <div style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span className="mono" style={{ fontSize: 10, color: '#6b5840', letterSpacing: '0.14em', textTransform: 'uppercase' }}>负重</span>
        <span className="mono" style={{ fontSize: 11, color: c }}>{load} / {max}</span>
      </div>
      <div style={{
        marginTop: 4,
        height: 8, background: 'rgba(107,88,64,0.18)',
        border: '1px solid rgba(107,88,64,0.5)',
        position: 'relative',
      }}>
        <div style={{
          width: `${pct * 100}%`,
          height: '100%',
          background: c,
        }} />
      </div>
    </div>
  );
}

window.Portrait = Portrait;
window.EncumbranceChip = EncumbranceChip;
