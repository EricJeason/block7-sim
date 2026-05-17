// pixel.jsx — pixel-art sprite components.
// All sprites are SVG rects in a 14x22 grid, image-rendering:pixelated.
// Direction: 's' (south/front), 'n', 'e', 'w'. Skin/hair/shirt/pants
// colors come from each NPC's palette in data.jsx.
//
// Style target: Stardew-clarity but muted palette to fit Mu Gu Zhen.

const PX = 4; // scale-up factor; 14*4=56, 22*4=88 visual

// Returns a list of <rect> JSX elements for an NPC pixel sprite.
// A pixel is defined as {x,y,w=1,h=1,c=color}.
function buildPixels(npc, dir = 's') {
  const skin = npc.skin;
  const hair = npc.hair;
  const shirt = npc.color;
  const accent = npc.accent;
  const pants = '#3a2e22';
  const boots = '#1a1410';
  const eye = '#1a1208';

  const px = [];

  // Helper to push rects easily
  const set = (x, y, c, w = 1, h = 1) => px.push({ x, y, c, w, h });

  // PANTS (rows 16-19)
  set(5, 16, pants, 4, 4);
  set(5, 20, boots, 4, 2);

  // BODY / SHIRT (rows 9-15)
  set(4, 9, shirt, 6, 7);
  // shoulder shading
  set(4, 9, accent, 1, 7);
  set(9, 9, accent, 1, 7);
  // belt
  set(4, 15, '#5a3a1a', 6, 1);
  // accent stripe down center
  set(6, 10, accent, 2, 5);

  // ARMS depending on dir
  if (dir === 's' || dir === 'n') {
    set(3, 10, shirt, 1, 5);
    set(10, 10, shirt, 1, 5);
    set(3, 14, skin, 1, 1);
    set(10, 14, skin, 1, 1);
  } else if (dir === 'e') {
    set(10, 11, shirt, 1, 4);
    set(11, 13, skin, 1, 1);
    set(3, 11, shirt, 1, 3); // back arm partly visible
  } else if (dir === 'w') {
    set(3, 11, shirt, 1, 4);
    set(2, 13, skin, 1, 1);
    set(10, 11, shirt, 1, 3);
  }

  // NECK
  set(6, 8, skin, 2, 1);

  // HEAD (rows 2-8)
  set(4, 3, skin, 6, 5); // face block
  set(4, 8, skin, 6, 1);
  // chin shading
  set(4, 7, '#c8a070', 1, 1);
  set(9, 7, '#c8a070', 1, 1);

  // HAIR
  if (dir === 's') {
    // top + front fringe
    set(4, 2, hair, 6, 2);
    set(3, 3, hair, 1, 3);
    set(10, 3, hair, 1, 3);
    set(4, 4, hair, 1, 1); // fringe
    set(9, 4, hair, 1, 1);
    // eyes
    set(5, 5, eye, 1, 1);
    set(8, 5, eye, 1, 1);
    // mouth
    set(7, 7, '#6b3a20', 1, 1);
  } else if (dir === 'n') {
    set(4, 2, hair, 6, 2);
    set(3, 3, hair, 1, 4);
    set(10, 3, hair, 1, 4);
    set(4, 4, hair, 6, 3); // big back of head
  } else if (dir === 'e') {
    set(4, 2, hair, 6, 2);
    set(3, 3, hair, 1, 4);
    set(10, 3, hair, 1, 4);
    set(4, 4, hair, 5, 1); // fringe swept
    set(8, 5, eye, 1, 1);
    set(9, 6, '#6b3a20', 1, 1);
  } else if (dir === 'w') {
    set(4, 2, hair, 6, 2);
    set(3, 3, hair, 1, 4);
    set(10, 3, hair, 1, 4);
    set(5, 4, hair, 5, 1);
    set(5, 5, eye, 1, 1);
    set(4, 6, '#6b3a20', 1, 1);
  }

  // Special NPC distinguishing marks
  if (npc.id === 4) {
    // Ailing — blue dress hem + golden long hair tail
    set(4, 16, '#5a6fa0', 6, 3);
    set(2, 8, hair, 1, 6); // side hair
    set(11, 8, hair, 1, 6);
  }
  if (npc.id === 5) {
    // Shen Yan — village chief, greying hair
    set(4, 2, '#9a8a72', 6, 2);
  }
  if (npc.id === 12) {
    // Bai Mo — elder, white hair + hood
    set(3, 2, '#dcd4c4', 8, 4);
    set(3, 5, '#dcd4c4', 1, 4);
    set(10, 5, '#dcd4c4', 1, 4);
  }
  if (npc.id === 9) {
    // Tian Zhu — blacksmith, leather apron
    set(4, 11, '#6b3a1a', 6, 5);
  }
  if (npc.id === 6) {
    // Qian Ling — patrol captain, shoulder strap
    set(3, 10, accent, 1, 6);
  }

  return px;
}

function PixelSprite({ npc, dir = 's', scale = PX, shadow = true }) {
  const pixels = buildPixels(npc, dir);
  const W = 14, H = 22;
  return (
    <div className="pixelated" style={{
      position: 'relative',
      width: W * scale, height: H * scale,
      pointerEvents: 'none'
    }}>
      {shadow && <div style={{
        position: 'absolute', left: '50%', bottom: -scale * 0.5,
        transform: 'translateX(-50%)',
        width: 10 * scale, height: 2 * scale,
        background: 'radial-gradient(ellipse, rgba(20,10,4,0.45), transparent 70%)',
        filter: 'blur(1px)'
      }}></div>}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        width={W * scale} height={H * scale}
        shapeRendering="crispEdges"
        style={{ position: 'absolute', inset: 0 }}
      >
        {pixels.map((p, i) => (
          <rect key={i} x={p.x} y={p.y} width={p.w} height={p.h} fill={p.c} />
        ))}
      </svg>
    </div>
  );
}

// A standing player avatar — uses NPC 4 (Ailing, the one with finished art).
// Player avatar gets a thin warm outline so they read as "you".
function PlayerSprite({ npc, dir = 's', scale = PX }) {
  return (
    <div style={{ position: 'relative', filter: 'drop-shadow(0 0 1.5px rgba(245,225,170,0.95))' }}>
      <PixelSprite npc={npc} dir={dir} scale={scale} />
    </div>
  );
}

// 5-direction grid for spec sheets: idle / walk N / S / E / W
function SpriteSheetRow({ npc, label }) {
  return (
    <div style={{ display: 'flex', gap: 18, alignItems: 'flex-end' }}>
      {['s', 'n', 'e', 'w'].map(d => (
        <div key={d} style={{ textAlign: 'center' }}>
          <PixelSprite npc={npc} dir={d} scale={4} />
          <div className="mono" style={{ fontSize: 10, color: '#6b5840', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.08em' }}>walk_{d}</div>
        </div>
      ))}
      <div style={{ textAlign: 'center' }}>
        <div style={{ position: 'relative' }}>
          <PixelSprite npc={npc} dir="s" scale={4} />
        </div>
        <div className="mono" style={{ fontSize: 10, color: '#6b5840', marginTop: 4, textTransform: 'uppercase', letterSpacing: '0.08em' }}>idle</div>
      </div>
      {label && (
        <div style={{ marginLeft: 14, alignSelf: 'center' }}>
          <div className="serif" style={{ fontSize: 22, color: '#3d2f1f', fontWeight: 600 }}>{npc.name}</div>
          <div className="mono" style={{ fontSize: 11, color: '#6b5840', marginTop: 2 }}>{npc.role}</div>
        </div>
      )}
    </div>
  );
}

window.PixelSprite = PixelSprite;
window.PlayerSprite = PlayerSprite;
window.SpriteSheetRow = SpriteSheetRow;
