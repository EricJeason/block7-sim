// scenes.jsx — pixel-art scene backgrounds.
// Each scene is rendered into a parent that's positioned absolute fill.
// viewBox uses a 320x180 working res, then scaled up + image-rendering:pixelated
// for a chunky Stardew-ish look.

function Scene({ id, day = 3, atmosphere = 'normal', children }) {
  const renderers = {
    plaza: PlazaScene,
    forge: ForgeScene,
    farm: FarmScene,
    tower: TowerScene,
  };
  const R = renderers[id];
  return (
    <div className="scene pixelated">
      <R day={day} atmosphere={atmosphere} />
      {children}
      {/* atmospheric layers */}
      {atmosphere === 'looming' && <LoomingOverlay />}
      {atmosphere === 'dusk' && <DuskOverlay />}
      {atmosphere === 'night' && <NightOverlay />}
    </div>
  );
}

// ---------------- LAO SONG PLAZA ----------------
function PlazaScene({ atmosphere }) {
  const sky = atmosphere === 'looming' ? '#d4b878' : '#e8c878';
  return (
    <svg viewBox="0 0 320 180" preserveAspectRatio="none" width="100%" height="100%" shapeRendering="crispEdges">
      {/* sky */}
      <rect x="0" y="0" width="320" height="74" fill={sky} />
      <rect x="0" y="62" width="320" height="12" fill="#c8a060" />
      {/* distant hills */}
      <path d="M0,74 L40,58 L70,68 L120,52 L170,66 L220,54 L270,68 L320,60 L320,82 L0,82 Z" fill="#7a8a5a" />
      <path d="M0,82 L60,72 L130,82 L200,74 L270,84 L320,76 L320,92 L0,92 Z" fill="#5a6b3a" />
      {/* ground — warm packed earth */}
      <rect x="0" y="92" width="320" height="88" fill="#a08560" />
      <rect x="0" y="92" width="320" height="6" fill="#8a6f4a" />
      {/* path stones */}
      {[40,80,120,160,200,240,280].map((x,i) => (
        <rect key={i} x={x} y={140} width="14" height="6" fill="#8a7050" />
      ))}
      {/* moss patches */}
      <rect x="20" y="120" width="22" height="3" fill="#6b7a3a" opacity="0.6" />
      <rect x="180" y="160" width="30" height="4" fill="#6b7a3a" opacity="0.55" />
      <rect x="260" y="130" width="24" height="3" fill="#6b7a3a" opacity="0.5" />

      {/* TAVERN (left) — dark wood */}
      <g>
        <rect x="20" y="64" width="76" height="60" fill="#6b3a1a" />
        <rect x="20" y="64" width="76" height="4" fill="#3a1a08" />
        {/* roof */}
        <path d="M14,68 L58,46 L102,68 Z" fill="#4a2a14" />
        <path d="M14,68 L58,46 L102,68 L102,72 L14,72 Z" fill="#3a1a08" />
        {/* door */}
        <rect x="48" y="92" width="18" height="32" fill="#2a1a08" />
        <rect x="48" y="92" width="18" height="3" fill="#5a3a1a" />
        {/* window */}
        <rect x="28" y="80" width="14" height="14" fill="#f0c878" />
        <rect x="72" y="80" width="14" height="14" fill="#f0c878" />
        <rect x="34" y="80" width="2" height="14" fill="#3a1a08" />
        <rect x="78" y="80" width="2" height="14" fill="#3a1a08" />
        {/* sign */}
        <rect x="36" y="76" width="42" height="6" fill="#8a5a32" />
        <rect x="55" y="68" width="2" height="8" fill="#3a1a08" />
      </g>

      {/* COUNCIL HALL (right) — stone */}
      <g>
        <rect x="220" y="58" width="84" height="66" fill="#c8b8a0" />
        <rect x="220" y="58" width="84" height="3" fill="#8a7860" />
        {/* roof */}
        <path d="M214,62 L262,38 L310,62 Z" fill="#7a5a3a" />
        <path d="M214,62 L262,38 L310,62 L310,66 L214,66 Z" fill="#5a3a1a" />
        {/* door */}
        <rect x="252" y="86" width="20" height="38" fill="#5a3a1a" />
        <rect x="252" y="86" width="20" height="3" fill="#3a1a08" />
        <rect x="261" y="98" width="2" height="20" fill="#3a1a08" />
        {/* arched windows */}
        <rect x="230" y="76" width="12" height="20" fill="#3a4a3a" />
        <rect x="282" y="76" width="12" height="20" fill="#3a4a3a" />
        {/* steps */}
        <rect x="244" y="124" width="36" height="4" fill="#a08570" />
        <rect x="238" y="128" width="48" height="4" fill="#8a7060" />
      </g>

      {/* CROOKED PINE — center */}
      <g>
        {/* trunk leaning right */}
        <path d="M152,124 L156,76 L162,40 L168,42 L164,80 L160,124 Z" fill="#3a2a18" />
        <path d="M156,76 L162,40 L168,42 L164,80 Z" fill="#5a3a22" opacity="0.5" />
        {/* needle clusters */}
        <ellipse cx="156" cy="48" rx="20" ry="14" fill="#3a4a2a" />
        <ellipse cx="170" cy="40" rx="14" ry="10" fill="#4a5a3a" />
        <ellipse cx="148" cy="58" rx="14" ry="10" fill="#2a3a1a" />
        <ellipse cx="178" cy="52" rx="10" ry="7" fill="#5a6b3a" />
      </g>

      {/* WELL — center-left */}
      <g>
        <rect x="78" y="106" width="22" height="14" fill="#7a6a52" />
        <rect x="76" y="104" width="26" height="4" fill="#a09080" />
        <rect x="84" y="108" width="10" height="10" fill="#1a1a2a" />
        {/* well roof posts */}
        <rect x="78" y="92" width="3" height="14" fill="#5a3a1a" />
        <rect x="97" y="92" width="3" height="14" fill="#5a3a1a" />
        <rect x="74" y="89" width="30" height="4" fill="#3a1a08" />
      </g>

      {/* corner bench (bottom right) */}
      <g>
        <rect x="262" y="148" width="30" height="3" fill="#5a3a1a" />
        <rect x="264" y="151" width="3" height="8" fill="#3a1a08" />
        <rect x="287" y="151" width="3" height="8" fill="#3a1a08" />
      </g>

      {/* east exit — path leading off */}
      <g>
        <path d="M296,108 L320,104 L320,124 L296,118 Z" fill="#8a7050" />
        <path d="M298,110 L318,108 L318,118 L298,116 Z" fill="#a08570" opacity="0.6" />
      </g>
    </svg>
  );
}

// ---------------- NORTH FROST WORKSHOP ----------------
function ForgeScene() {
  return (
    <svg viewBox="0 0 320 180" preserveAspectRatio="none" width="100%" height="100%" shapeRendering="crispEdges">
      {/* cold sky */}
      <rect x="0" y="0" width="320" height="72" fill="#8a9eb4" />
      <rect x="0" y="58" width="320" height="14" fill="#6e8298" />
      {/* snow-capped mountains */}
      <path d="M0,72 L50,40 L80,56 L130,30 L180,52 L220,38 L260,58 L320,46 L320,82 L0,82 Z" fill="#4a5a6e" />
      <path d="M50,40 L62,46 L74,40 Z" fill="#dce4ec" />
      <path d="M130,30 L142,38 L154,30 Z" fill="#dce4ec" />
      <path d="M220,38 L232,44 L244,38 Z" fill="#dce4ec" />

      {/* snowy ground */}
      <rect x="0" y="82" width="320" height="98" fill="#3a4a58" />
      <rect x="0" y="82" width="320" height="22" fill="#5a6e80" opacity="0.55" />
      {/* snow patches */}
      <rect x="20" y="120" width="40" height="6" fill="#c8d4e0" opacity="0.75" />
      <rect x="120" y="140" width="60" height="8" fill="#c8d4e0" opacity="0.65" />
      <rect x="240" y="130" width="56" height="6" fill="#c8d4e0" opacity="0.7" />

      {/* WORKSHOP (center-left) — stone + dark wood with glowing forge mouth */}
      <g>
        <rect x="40" y="50" width="100" height="74" fill="#5a4030" />
        <rect x="40" y="50" width="100" height="4" fill="#3a2418" />
        <rect x="40" y="118" width="100" height="6" fill="#3a2418" />
        {/* roof */}
        <path d="M34,54 L90,30 L146,54 Z" fill="#3a2a1a" />
        <path d="M34,54 L90,30 L146,54 L146,58 L34,58 Z" fill="#1a1408" />
        {/* forge mouth — orange glow */}
        <rect x="62" y="84" width="34" height="34" fill="#1a0a04" />
        <rect x="68" y="92" width="22" height="22" fill="#d87a3a" />
        <rect x="72" y="96" width="14" height="14" fill="#f4c878" />
        <rect x="76" y="100" width="6" height="6" fill="#ffffff" opacity="0.6" />
        {/* chimney */}
        <rect x="106" y="20" width="14" height="34" fill="#3a2418" />
        <rect x="104" y="18" width="18" height="4" fill="#1a0e08" />
        {/* smoke */}
        <ellipse cx="113" cy="10" rx="14" ry="6" fill="#7a8898" opacity="0.6" />
        <ellipse cx="120" cy="2" rx="18" ry="6" fill="#7a8898" opacity="0.4" />
        {/* window */}
        <rect x="108" y="74" width="20" height="18" fill="#1a1a2a" />
        <rect x="116" y="74" width="2" height="18" fill="#3a2418" />
      </g>

      {/* anvil */}
      <g>
        <rect x="160" y="124" width="22" height="12" fill="#2a2a32" />
        <rect x="162" y="120" width="18" height="6" fill="#3a3a44" />
        <rect x="166" y="136" width="10" height="6" fill="#1a1a22" />
      </g>

      {/* WEAPON RACK (right) */}
      <g>
        <rect x="210" y="100" width="40" height="6" fill="#3a2418" />
        <rect x="210" y="120" width="40" height="6" fill="#3a2418" />
        {[214, 222, 230, 238, 246].map((x,i) => (
          <rect key={i} x={x} y="92" width="2" height="32" fill="#c8c0b0" />
        ))}
      </g>

      {/* ICE/FROST ORE PILE (bottom-left) */}
      <g>
        <path d="M14,150 L38,140 L62,150 L62,168 L14,168 Z" fill="#6e8aa4" />
        <path d="M14,150 L38,140 L62,150 L52,152 L38,144 L24,152 Z" fill="#a0bcd4" />
        <rect x="24" y="148" width="4" height="6" fill="#dce4ec" opacity="0.7" />
        <rect x="42" y="146" width="4" height="6" fill="#dce4ec" opacity="0.7" />
      </g>

      {/* LOOKOUT TOWER (far back right) */}
      <g>
        <rect x="270" y="38" width="22" height="50" fill="#3a2418" />
        <rect x="266" y="34" width="30" height="6" fill="#2a1810" />
        <rect x="278" y="48" width="6" height="10" fill="#1a1a2a" />
        <rect x="268" y="88" width="26" height="6" fill="#2a1810" />
      </g>

      {/* patrol exit — east */}
      <path d="M298,118 L320,116 L320,134 L298,130 Z" fill="#6e8298" opacity="0.6" />
    </svg>
  );
}

// ---------------- WARM VALLEY FARM ----------------
function FarmScene({ atmosphere }) {
  return (
    <svg viewBox="0 0 320 180" preserveAspectRatio="none" width="100%" height="100%" shapeRendering="crispEdges">
      {/* warm pale sky */}
      <rect x="0" y="0" width="320" height="68" fill="#dce8b8" />
      <rect x="0" y="54" width="320" height="14" fill="#c8d8a0" />
      {/* layered ridges */}
      <path d="M0,68 L60,52 L110,62 L170,50 L230,60 L290,52 L320,60 L320,84 L0,84 Z" fill="#7a9560" />
      <path d="M0,84 L80,76 L150,84 L220,78 L300,86 L320,82 L320,98 L0,98 Z" fill="#5a7340" />

      {/* lush ground */}
      <rect x="0" y="98" width="320" height="82" fill="#6b7e44" />
      <rect x="0" y="98" width="320" height="8" fill="#8aa05a" opacity="0.7" />

      {/* herb rows */}
      {[0,1,2,3,4].map(i => (
        <rect key={i} x={20 + i*16} y={150} width="10" height="3" fill="#3a5a2a" />
      ))}
      {[0,1,2,3,4].map(i => (
        <rect key={i} x={20 + i*16} y={156} width="10" height="3" fill="#3a5a2a" />
      ))}
      {/* flowers among herbs */}
      <rect x="26" y="148" width="2" height="2" fill="#c8b864" />
      <rect x="58" y="148" width="2" height="2" fill="#e8a8b0" />

      {/* GREENHOUSE (left) */}
      <g>
        <rect x="20" y="74" width="60" height="48" fill="#b8d4d0" opacity="0.7" />
        <rect x="20" y="74" width="60" height="48" fill="none" stroke="#3a2a1a" strokeWidth="1" />
        {/* frame */}
        <rect x="48" y="74" width="2" height="48" fill="#3a2a1a" />
        <rect x="20" y="96" width="60" height="2" fill="#3a2a1a" />
        {/* roof glass */}
        <path d="M14,76 L50,58 L86,76 Z" fill="#a0c4c0" opacity="0.85" />
        <path d="M14,76 L50,58 L86,76" stroke="#3a2a1a" strokeWidth="1" fill="none" />
        <line x1="50" y1="58" x2="50" y2="76" stroke="#3a2a1a" strokeWidth="1" />
        {/* door */}
        <rect x="42" y="100" width="16" height="22" fill="#5a3a1a" />
      </g>

      {/* "STRANGE FLOWER" TREE — center, the one blooming out of season */}
      <g>
        <path d="M170,122 L172,82 L178,50 L184,52 L180,84 L178,122 Z" fill="#4a3018" />
        {/* trunk shading */}
        <path d="M172,82 L178,50 L184,52 L180,84 Z" fill="#6b4a2a" opacity="0.5" />
        {/* foliage */}
        <ellipse cx="172" cy="58" rx="22" ry="16" fill="#5a7340" />
        <ellipse cx="186" cy="48" rx="14" ry="10" fill="#6b8a4a" />
        <ellipse cx="164" cy="68" rx="14" ry="10" fill="#3a5a2a" />
        {/* unsettling lilac blossoms — these "should not be in bloom" */}
        <rect x="158" y="46" width="2" height="2" fill="#c8a4d4" />
        <rect x="166" y="42" width="2" height="2" fill="#d4b4dc" />
        <rect x="178" y="40" width="2" height="2" fill="#c8a4d4" />
        <rect x="186" y="46" width="2" height="2" fill="#d4b4dc" />
        <rect x="194" y="50" width="2" height="2" fill="#c8a4d4" />
        <rect x="172" y="56" width="2" height="2" fill="#d4b4dc" />
        <rect x="184" y="60" width="2" height="2" fill="#c8a4d4" />
        <rect x="162" y="62" width="2" height="2" fill="#d4b4dc" />
        {/* fallen petals */}
        <rect x="172" y="124" width="2" height="2" fill="#c8a4d4" opacity="0.7" />
        <rect x="180" y="126" width="2" height="2" fill="#c8a4d4" opacity="0.6" />
      </g>

      {/* spring/well */}
      <g>
        <ellipse cx="240" cy="130" rx="22" ry="6" fill="#3a5a6a" />
        <ellipse cx="240" cy="128" rx="20" ry="5" fill="#5a7a8a" />
        <rect x="222" y="126" width="38" height="2" fill="#a0bcc8" opacity="0.6" />
      </g>

      {/* main house porch (left edge) */}
      <g>
        <rect x="2" y="118" width="14" height="32" fill="#6b4a2a" />
        <rect x="2" y="114" width="18" height="6" fill="#4a3018" />
        <rect x="6" y="128" width="6" height="14" fill="#3a1a08" />
      </g>

      {/* wooden fence gate (right edge) */}
      <g>
        <rect x="282" y="110" width="4" height="24" fill="#6b4a2a" />
        <rect x="302" y="110" width="4" height="24" fill="#6b4a2a" />
        <rect x="280" y="116" width="28" height="3" fill="#5a3a1a" />
        <rect x="280" y="126" width="28" height="3" fill="#5a3a1a" />
      </g>
    </svg>
  );
}

// ---------------- SILENT TOWER RUINS ----------------
function TowerScene() {
  return (
    <svg viewBox="0 0 320 180" preserveAspectRatio="none" width="100%" height="100%" shapeRendering="crispEdges">
      {/* overcast bruised sky */}
      <rect x="0" y="0" width="320" height="74" fill="#6e7080" />
      <rect x="0" y="60" width="320" height="14" fill="#54566a" />

      {/* far trees */}
      <path d="M0,74 L30,58 L60,72 L100,54 L140,70 L180,56 L220,72 L260,58 L320,70 L320,86 L0,86 Z" fill="#3a3a48" />
      <path d="M0,86 L60,78 L130,88 L200,80 L270,90 L320,82 L320,98 L0,98 Z" fill="#2a2a36" />

      {/* desolate ground */}
      <rect x="0" y="98" width="320" height="82" fill="#3a3a44" />
      <rect x="0" y="98" width="320" height="8" fill="#54566a" opacity="0.55" />
      {/* dead grass tufts */}
      {[24, 70, 130, 200, 260, 296].map((x, i) => (
        <g key={i}>
          <rect x={x} y={140} width="2" height="4" fill="#6b6850" />
          <rect x={x+3} y={142} width="2" height="3" fill="#6b6850" />
        </g>
      ))}

      {/* BROKEN TOWER — center */}
      <g>
        {/* base */}
        <rect x="142" y="74" width="46" height="56" fill="#7a7886" />
        <rect x="142" y="74" width="46" height="4" fill="#5a586a" />
        {/* stone block lines */}
        <line x1="142" y1="92" x2="188" y2="92" stroke="#5a586a" strokeWidth="1" />
        <line x1="142" y1="110" x2="188" y2="110" stroke="#5a586a" strokeWidth="1" />
        <line x1="158" y1="74" x2="158" y2="92" stroke="#5a586a" strokeWidth="1" />
        <line x1="172" y1="92" x2="172" y2="110" stroke="#5a586a" strokeWidth="1" />
        {/* upper truncated half — the snapped-off tower */}
        <path d="M148,74 L154,50 L158,46 L168,42 L162,74 Z" fill="#6a6878" />
        <path d="M168,42 L176,38 L182,48 L188,74 L162,74 Z" fill="#54566a" />
        {/* jagged top — where it broke */}
        <path d="M148,74 L156,72 L162,76 L172,72 L182,76 L188,72 L188,76 L148,76 Z" fill="#3a3a48" />
        {/* burnt inscription — a dark scorched scar across the stone */}
        <rect x="146" y="98" width="40" height="6" fill="#1a1410" opacity="0.85" />
        <rect x="146" y="98" width="40" height="2" fill="#2a1a14" opacity="0.9" />
        {/* tiny remnant glyph fragments */}
        <rect x="150" y="100" width="1" height="2" fill="#6b3a20" opacity="0.6" />
        <rect x="166" y="100" width="1" height="2" fill="#6b3a20" opacity="0.6" />
        <rect x="180" y="100" width="1" height="2" fill="#6b3a20" opacity="0.6" />
        {/* arched doorway at base */}
        <path d="M158,118 L158,130 L172,130 L172,118 Q165,110 158,118 Z" fill="#1a141a" />
      </g>

      {/* rubble pile (right side) */}
      <g>
        <path d="M198,142 L240,128 L264,142 L264,158 L198,158 Z" fill="#5a586a" />
        <path d="M198,142 L240,128 L264,142 L252,144 L240,134 L226,144 Z" fill="#7a7886" />
        <rect x="218" y="138" width="6" height="4" fill="#3a3a48" />
        <rect x="240" y="138" width="6" height="4" fill="#3a3a48" />
      </g>

      {/* a fallen, half-buried stele (left) */}
      <g>
        <rect x="44" y="138" width="48" height="10" fill="#6a6878" transform="rotate(-8 68 143)" />
        <rect x="46" y="140" width="42" height="2" fill="#3a3a48" transform="rotate(-8 68 143)" opacity="0.7" />
      </g>

      {/* beast trail leading off east */}
      <path d="M268,118 L320,114 L320,134 L268,128 Z" fill="#2a2a36" opacity="0.85" />
      <path d="M276,120 L316,118 L316,128 L276,126 Z" fill="#3a3a44" opacity="0.7" />
    </svg>
  );
}

// ---------------- atmosphere overlays ----------------
function LoomingOverlay() {
  return (
    <>
      {/* color-temp shift cooler + slight desaturation tint */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'linear-gradient(180deg, rgba(50,40,80,0.18) 0%, rgba(40,30,60,0.10) 60%, rgba(20,10,30,0.18) 100%)',
        mixBlendMode: 'multiply'
      }} />
      {/* haze */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none',
        background: 'radial-gradient(ellipse at 50% 30%, rgba(180,170,200,0.18), transparent 70%)'
      }} />
    </>
  );
}
function DuskOverlay() {
  return (
    <div style={{
      position: 'absolute', inset: 0, pointerEvents: 'none',
      background: 'linear-gradient(180deg, rgba(230,140,80,0.22) 0%, rgba(120,60,80,0.18) 60%, rgba(40,20,40,0.20) 100%)',
      mixBlendMode: 'multiply'
    }} />
  );
}
function NightOverlay() {
  return (
    <div style={{
      position: 'absolute', inset: 0, pointerEvents: 'none',
      background: 'linear-gradient(180deg, rgba(20,20,50,0.55) 0%, rgba(10,10,30,0.60) 100%)',
      mixBlendMode: 'multiply'
    }} />
  );
}

window.Scene = Scene;
