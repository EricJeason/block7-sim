// main-screen.jsx — S3 interactive main view.
// Renders a 1280x720 scene with the player, NPCs at anchor points,
// HUD chrome (clock + location label + key hints), and handles
// keyboard for WASD / E / Q / F / Esc / T / R.

const SCREEN_W = 1280;
const SCREEN_H = 720;
const SCENE_NATIVE_W = 1280; // anchor coord system

// Distance threshold to "see" an NPC's action whisper
const HOVER_RADIUS = 140;
// Distance for E-key interaction target
const INTERACT_RADIUS = 110;

function MainScreen({ initialLoc = 'plaza', day = 3, hour = 15, minute = 52, atmosphere = 'normal', showHealerHint = false, showCracks = false, embedded = false }) {
  const loc = LOCATIONS[initialLoc];
  const playerNpc = NPCS[3]; // Ailing (finished art)

  // player position (in SCENE coords)
  const [pos, setPos] = React.useState({ x: 620, y: 540 });
  const [facing, setFacing] = React.useState('s');
  const [modal, setModal] = React.useState(null); // 'menu' | 'Q' | 'F' | 'Esc' | 'T' | 'R' | 'S11'
  const [bubbleSelected, setBubbleSelected] = React.useState(0);
  const [paused, setPaused] = React.useState(false);

  // NPC positions: pinned to anchors
  const placements = React.useMemo(() => {
    const here = NPCS.filter(n => n.loc === initialLoc);
    return here.map((n, i) => {
      const a = loc.anchors[i % loc.anchors.length];
      return { npc: n, x: a.x, y: a.y, anchor: a };
    });
  }, [initialLoc, loc]);

  // Closest NPC for interaction
  const target = React.useMemo(() => {
    let best = null, bestD = Infinity;
    placements.forEach(p => {
      const dx = p.x - pos.x, dy = p.y - pos.y;
      const d = Math.hypot(dx, dy);
      if (d < bestD) { bestD = d; best = { ...p, d }; }
    });
    return best;
  }, [placements, pos]);

  // Keyboard handling
  React.useEffect(() => {
    const keys = {};
    const onDown = (e) => {
      keys[e.key.toLowerCase()] = true;
      if (modal) {
        if (e.key === 'Escape') { setModal(null); }
        if (modal === 'menu') {
          if (e.key === 'ArrowUp')   { e.preventDefault(); setBubbleSelected(s => Math.max(0, s - 1)); }
          if (e.key === 'ArrowDown') { e.preventDefault(); setBubbleSelected(s => Math.min(2, s + 1)); }
          if (e.key === 'Enter')     { e.preventDefault();
            if (bubbleSelected === 1) setModal('S11'); // read mind sketch -> dialogue stand-in
            else if (bubbleSelected === 0) setModal('S11');
            else setModal(null);
          }
        }
        return;
      }
      if (e.key.toLowerCase() === 'e' && target && target.d < INTERACT_RADIUS) {
        setModal('menu'); setBubbleSelected(0);
      } else if (e.key.toLowerCase() === 'q') setModal('Q');
      else if (e.key.toLowerCase() === 'f') setModal('F');
      else if (e.key.toLowerCase() === 't') setModal('T');
      else if (e.key.toLowerCase() === 'r') setModal('R');
      else if (e.key.toLowerCase() === 'c') setModal('C');
      else if (e.key.toLowerCase() === 'i') setModal('I');
      else if (e.key.toLowerCase() === 'j') setModal('J');
      else if (e.key.toLowerCase() === 'p') setModal('P');
      else if (e.key === 'Escape') setModal('Esc');
      else if (e.key === 'Tab')    { e.preventDefault(); setPaused(p => !p); }
    };
    const onUp = (e) => { delete keys[e.key.toLowerCase()]; };
    window.addEventListener('keydown', onDown);
    window.addEventListener('keyup', onUp);

    // movement tick
    let raf, last = performance.now();
    const tick = (t) => {
      const dt = Math.min(48, t - last); last = t;
      if (!modal && !paused) {
        const speed = 0.25; // px / ms
        let dx = 0, dy = 0;
        if (keys['w'] || keys['arrowup'])    dy -= 1;
        if (keys['s'] || keys['arrowdown'])  dy += 1;
        if (keys['a'] || keys['arrowleft'])  dx -= 1;
        if (keys['d'] || keys['arrowright']) dx += 1;
        if (dx || dy) {
          const L = Math.hypot(dx, dy);
          dx /= L; dy /= L;
          setPos(p => ({
            x: Math.max(60, Math.min(SCENE_NATIVE_W - 60, p.x + dx * speed * dt)),
            y: Math.max(380, Math.min(SCREEN_H - 40, p.y + dy * speed * dt)),
          }));
          if (Math.abs(dx) > Math.abs(dy)) setFacing(dx > 0 ? 'e' : 'w');
          else                              setFacing(dy > 0 ? 's' : 'n');
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => { window.removeEventListener('keydown', onDown); window.removeEventListener('keyup', onUp); cancelAnimationFrame(raf); };
  }, [target, modal, paused, bubbleSelected]);

  const inRange = target && target.d < INTERACT_RADIUS;
  const hovered = target && target.d < HOVER_RADIUS ? target : null;

  return (
    <div
      style={{
        position: 'relative',
        width: SCREEN_W, height: SCREEN_H,
        background: '#1a140c',
        overflow: 'hidden',
        userSelect: 'none',
      }}
      tabIndex={0}
      onMouseEnter={(e) => e.currentTarget.focus()}
    >
      {/* SCENE LAYER (pixelated) */}
      <div style={{ position: 'absolute', inset: 0, transform: 'scale(1)', transformOrigin: 'top left' }}>
        <Scene id={loc.id} day={day} atmosphere={atmosphere} />
      </div>

      {/* vignette */}
      <div className="vignette" style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <div style={{ position: 'absolute', inset: 0 }} />
      </div>

      {/* NPCs (z-sorted by y) */}
      {placements
        .map((p, i) => ({ ...p, i }))
        .sort((a, b) => a.y - b.y)
        .map(p => {
          const isTarget = target && target.npc.id === p.npc.id;
          const inHover  = hovered && hovered.npc.id === p.npc.id;
          const inSelect = isTarget && inRange;
          const action = ACTIONS[p.npc.id] || p.npc.role;
          // mock load — varies per npc id deterministically
          const load = (p.npc.id * 3) % 11;
          return (
            <div key={p.npc.id} style={{
              position: 'absolute',
              left: p.x, top: p.y,
              transform: 'translate(-50%, -100%)',
              zIndex: Math.round(p.y),
            }}>
              {inHover && (
                <div style={{
                  position: 'absolute',
                  bottom: '100%', left: '50%', transform: 'translate(-50%, -2px)',
                  marginBottom: 4,
                  display: 'flex', flexDirection: 'column', alignItems: 'center'
                }}>
                  <HoverWhisper name={p.npc.name} text={action} load={load} max={10} />
                </div>
              )}
              <div className={inSelect ? 'selpulse' : ''} style={{
                borderRadius: '50%',
                padding: inSelect ? 2 : 0,
                filter: showHealerHint && p.npc.healer ? 'drop-shadow(0 0 4px rgba(122,90,150,0.45))' : 'none'
              }}>
                <PixelSprite npc={p.npc} dir="s" scale={4} />
              </div>
              {/* dream particle for healers when atmosphere = night */}
              {showHealerHint && p.npc.healer && atmosphere === 'night' && (
                <div style={{ position: 'absolute', left: '50%', top: 4 }}>
                  <span className="dreamparticle" />
                </div>
              )}
            </div>
          );
        })}

      {/* PLAYER sprite */}
      <div style={{
        position: 'absolute',
        left: pos.x, top: pos.y,
        transform: 'translate(-50%, -100%)',
        zIndex: Math.round(pos.y) + 1,
      }}>
        <PlayerSprite npc={playerNpc} dir={facing} scale={4} />
        {/* "YOU" tag floats subtly */}
        <div className="mono" style={{
          position: 'absolute', left: '50%', top: -14, transform: 'translate(-50%, 0)',
          fontSize: 9, color: 'rgba(245,235,200,0.85)', letterSpacing: '0.18em',
          textShadow: '0 1px 2px rgba(0,0,0,0.6)'
        }}>YOU</div>
      </div>

      {/* E-prompt floats above target NPC when in range */}
      {inRange && modal !== 'menu' && (
        <div style={{
          position: 'absolute',
          left: target.x, top: target.y - 100,
          transform: 'translate(-50%, -100%)',
          zIndex: 1000,
          display: 'flex', alignItems: 'center', gap: 6
        }}>
          <KeyCap>E</KeyCap>
          <span className="serif" style={{
            fontSize: 13, color: '#3d2f1f',
            background: 'rgba(232,220,196,0.9)',
            border: '1px solid rgba(107,88,64,0.5)',
            padding: '1px 8px', borderRadius: 2
          }}>互动</span>
        </div>
      )}

      {/* TOP CENTER · wood plank clock */}
      <div style={{ position: 'absolute', top: -4, left: '50%', transform: 'translateX(-50%)', zIndex: 50 }}>
        <WoodClock day={day} hour={hour} minute={minute} cracked={showCracks} />
      </div>

      {/* BOTTOM LEFT · location label */}
      <div style={{ position: 'absolute', left: 32, bottom: 28, zIndex: 50 }}>
        <LocationLabel name={loc.name} en={loc.en} count={placements.length} />
      </div>

      {/* BOTTOM RIGHT · key hints */}
      <div style={{ position: 'absolute', right: 32, bottom: 28, zIndex: 50 }}>
        <KeyHints hints={[
          { key: 'E', label: inRange ? `与 ${target.npc.name} 互动` : '靠近 NPC 互动' },
          { key: 'C', label: '角色' },
          { key: 'I', label: '背包' },
          { key: 'J', label: '线索 / 任务' },
          { key: 'P', label: '图鉴' },
          { key: 'Q', label: '场所概览' },
          { key: 'F', label: '读自己的心' },
          { key: 'Esc', label: '菜单' },
        ]} />
      </div>

      {/* PAUSED chip */}
      {paused && (
        <div className="mono" style={{
          position: 'absolute', top: 60, left: '50%', transform: 'translateX(-50%)',
          fontSize: 11, color: '#3d2f1f',
          background: 'rgba(232,220,196,0.9)',
          border: '1px solid rgba(107,88,64,0.55)',
          padding: '3px 10px', borderRadius: 2,
          letterSpacing: '0.2em', zIndex: 51
        }}>· PAUSED · TAB</div>
      )}

      {/* MODALS */}
      {modal === 'menu' && target && (
        <div style={{
          position: 'absolute',
          left: target.x, top: target.y - 110,
          transform: 'translate(-50%, -100%)',
          zIndex: 200,
        }}>
          <BubbleMenu
            npc={target.npc}
            selected={bubbleSelected}
            options={[
              { label: '打招呼' },
              { label: '读心', cost: '× 限 1' },
              { label: '离开' },
            ]}
          />
        </div>
      )}

      {modal === 'Q' && (
        <LocationCard loc={loc} npcs={NPCS} day={day} hour={hour} minute={minute} onClose={() => setModal(null)} />
      )}

      {modal === 'Esc' && (
        <SystemMenu onClose={() => setModal(null)} day={day} hour={hour} minute={minute} />
      )}

      {modal === 'F' && (
        <InnerHeart
          playerNpc={playerNpc}
          reflections={[
            { text: '昨夜又梦见配药材。手很稳,却记不得是为谁配的。' },
            { text: '父亲的笔记里有一页被撕掉了——我一直没敢问母亲。' },
            { text: '寂塔的方向,起雾的时候会响。' },
            { text: '若大魔潮真的近了——我希望我还记得自己是谁。' },
          ]}
          onClose={() => setModal(null)}
        />
      )}

      {modal === 'T' && (
        <EventLog events={EVENTS} day={day} onClose={() => setModal(null)} />
      )}

      {modal === 'R' && (
        <RelationshipNetwork npcs={NPCS} player={playerNpc} onClose={() => setModal(null)} />
      )}

      {modal === 'C' && (
        <CharacterPanel npc={playerNpc} onClose={() => setModal(null)} />
      )}
      {modal === 'I' && (
        <InventoryPanel player={playerNpc} onClose={() => setModal(null)} />
      )}
      {modal === 'J' && (
        <QuestBook onClose={() => setModal(null)} />
      )}
      {modal === 'P' && (
        <CodexPanel onClose={() => setModal(null)} />
      )}

      {modal === 'S11' && target && (
        <DialogueSession
          player={playerNpc}
          npc={target.npc}
          lines={{
            current: '“你今早去过井边吗?我看着水有些发暗——也许只是错觉。”',
            choices: [
              '“你最近也睡得不安稳吧。”',
              '“没什么,我应该回去看看温棚。”',
              '(沉默地点头)',
            ]
          }}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
}

window.MainScreen = MainScreen;
