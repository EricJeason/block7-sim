// data.jsx — world data shared across all artboards
// NPCs, locations, anchor points, sample dialogue lines.

const NPCS = [
  { id: 1,  name: '林秋',   role: '村医',         color: '#7e9d6a', skin: '#e8d0a8', hair: '#3a2418', accent: '#4a6b3a', healer: true,  loc: 'farm'  },
  { id: 2,  name: '阿杏',   role: '林秋徒弟',     color: '#c89a5e', skin: '#f0d6ad', hair: '#2a1810', accent: '#8b6f3a', healer: true,  loc: 'farm'  },
  { id: 3,  name: '早纪',   role: '协会驻村员',   color: '#8a7faa', skin: '#e6cea4', hair: '#1a1a1a', accent: '#3a3a5a', healer: false, loc: 'plaza' },
  { id: 4,  name: '艾琳',   role: '客居研究员',   color: '#c8b66e', skin: '#f4dcb4', hair: '#d4b454', accent: '#5a6fa0', healer: false, loc: 'tower' },
  { id: 5,  name: '沈砚',   role: '村长',         color: '#7a6a52', skin: '#d8b890', hair: '#9a8a72', accent: '#5a4a32', healer: false, loc: 'plaza' },
  { id: 6,  name: '千绫',   role: '捕魔队长',     color: '#5a7a8a', skin: '#e0c0a0', hair: '#2a2018', accent: '#c87a3a', healer: false, loc: 'forge' },
  { id: 7,  name: '苏拂',   role: '酒馆老板',     color: '#a8744a', skin: '#e8c8a0', hair: '#3a2a1a', accent: '#6b3a20', healer: false, loc: 'plaza' },
  { id: 8,  name: '马九',   role: '跑商',         color: '#8a6a3a', skin: '#d8b080', hair: '#2a1a0a', accent: '#5a3a1a', healer: false, loc: 'plaza' },
  { id: 9,  name: '田柱',   role: '铁匠',         color: '#6b4a32', skin: '#c8a070', hair: '#1a0e08', accent: '#a06030', healer: false, loc: 'forge' },
  { id: 10, name: '文姐',   role: '农场主',       color: '#9aa86a', skin: '#e6c8a0', hair: '#3a2a18', accent: '#7a8a4a', healer: false, loc: 'farm'  },
  { id: 11, name: '小璎',   role: '捕魔队员',     color: '#7a8aa0', skin: '#e8d0a8', hair: '#1a1a1a', accent: '#c0904a', healer: false, loc: 'forge' },
  { id: 12, name: '白嬤',   role: '村中老人',     color: '#a8a094', skin: '#d4b890', hair: '#dcd4c4', accent: '#6b5840', healer: true,  loc: 'plaza' },
];

const LOCATIONS = {
  plaza: {
    id: 'plaza',
    name: '老松广场',
    en: 'Old Pine Plaza',
    mood: '中央枢纽 · 歪脖子老松 · 酒馆 · 议事厅',
    tone: { sky: '#f0d8a0', mid: '#c8a878', ground: '#6b5a3a', accent: '#7a8f5a' },
    anchors: [
      { id: 'well',     label: '井边',       x: 340, y: 520 },
      { id: 'tavern',   label: '酒馆门口',   x: 180, y: 600 },
      { id: 'pine',     label: '老松下',     x: 640, y: 460 },
      { id: 'hall',     label: '议事厅前',   x: 820, y: 380 },
      { id: 'center',   label: '广场中央',   x: 500, y: 540 },
      { id: 'bench',    label: '角落长椅',   x: 1050, y: 620 },
      { id: 'gate_e',   label: '东出口',     x: 1180, y: 440 },
    ]
  },
  forge: {
    id: 'forge',
    name: '北霜工坊',
    en: 'North Frost Workshop',
    mood: '寒带 · 提炼霜髓矿 · 捕魔队驻地',
    tone: { sky: '#8aa0b8', mid: '#5e7a90', ground: '#3a4a58', accent: '#d87a3a' },
    anchors: [
      { id: 'forge',    label: '炉口',       x: 380, y: 500 },
      { id: 'anvil',    label: '铁砧旁',     x: 540, y: 540 },
      { id: 'rack',     label: '武器架',     x: 700, y: 460 },
      { id: 'lookout',  label: '了望台',     x: 900, y: 360 },
      { id: 'ice_pile', label: '霜矿堆',     x: 200, y: 580 },
      { id: 'patrol',   label: '巡逻入口',   x: 1100, y: 480 },
    ]
  },
  farm: {
    id: 'farm',
    name: '暖谷农场',
    en: 'Warm Valley Farm',
    mood: '热带山谷 · 草药 · 温棚 · 故乡小树',
    tone: { sky: '#dce8b8', mid: '#8aa56a', ground: '#5a6b3a', accent: '#b89cc4' },
    anchors: [
      { id: 'tree',     label: '故乡小树',   x: 640, y: 440 },
      { id: 'green',    label: '温棚',       x: 280, y: 500 },
      { id: 'herb',     label: '草药圃',     x: 460, y: 560 },
      { id: 'well',     label: '泉眼',       x: 820, y: 540 },
      { id: 'gate',     label: '木栅栏',     x: 1080, y: 480 },
      { id: 'porch',    label: '主屋廊下',   x: 160, y: 600 },
    ]
  },
  tower: {
    id: 'tower',
    name: '寂塔遗迹',
    en: 'Silent Tower Ruins',
    mood: '倒了一半的石塔 · 塔身刻字被烧掉 · 野兽小径',
    tone: { sky: '#7a7a8a', mid: '#4a4a5a', ground: '#3a3a48', accent: '#7a5a8a' },
    anchors: [
      { id: 'tower',    label: '塔基',       x: 540, y: 460 },
      { id: 'burnt',    label: '被烧的刻字', x: 380, y: 420 },
      { id: 'rubble',   label: '碎石堆',     x: 720, y: 540 },
      { id: 'trail',    label: '野兽小径',   x: 1040, y: 500 },
      { id: 'shrine',   label: '残碑',       x: 240, y: 560 },
      { id: 'edge',     label: '林缘',       x: 900, y: 600 },
    ]
  },
};

// Sample current-action lines (LLM would generate these — these are stand-ins)
const ACTIONS = {
  3:  '在井边读手里的协会档案',
  5:  '坐在议事厅前的台阶上',
  7:  '擦酒馆门口的木牌',
  8:  '清点广场中央的货箱',
  12: '站在老松下,数手里的落叶',
};

// Bigger-event log items for T panel
const EVENTS = [
  { day: 3, time: '06:14', text: '马九清晨进村,带回西边的消息。', tag: '听闻' },
  { day: 3, time: '09:02', text: '阿杏在草药圃醒来,说梦见配药材。', tag: '心声' },
  { day: 3, time: '11:47', text: '艾琳独自走向寂塔遗迹方向。', tag: '行动' },
  { day: 2, time: '21:30', text: '酒馆里的人比平时安静了一些。', tag: '氛围' },
  { day: 2, time: '15:12', text: '田柱在炉边敲打一把没刻完字的刀。', tag: '行动' },
  { day: 1, time: '19:05', text: '白嬤把陶罐里的落叶倒出来又装了一次。', tag: '异常' },
];

window.NPCS = NPCS;
window.LOCATIONS = LOCATIONS;
window.ACTIONS = ACTIONS;
window.EVENTS = EVENTS;
