/**
 * blobPresets.js
 * Design system palette, presets, and utility helpers for Grok Blob Mascots.
 */

export const BLOB_COLORS = {
  orange: '#FF5C35', // Grok Signature Warm Orange
  coral: '#FF6B4A',  // Punchy Vivid Coral
  sky: '#358BFF',    // Electric Sky Blue
  blue: '#3B82F6',   // Bold Primary Blue
  yellow: '#FFC700', // Grok Vivid Yellow
  lime: '#EAB308',   // Playful Lime Gold
  purple: '#9B51E0', // Deep Creative Purple
  violet: '#A855F7', // Bright Neon Violet
  mint: '#10B981',   // Fresh Mint Green
  green: '#27AE60',  // Emerald Green
  pink: '#FF76A5',   // Sweet Candy Pink
  rose: '#F43F5E',   // Vivid Rose Red
  dark: '#2D3748',   // Sleek Slate / Grok Dark
};

export const BLOB_COLOR_LIST = Object.values(BLOB_COLORS);

export const BLOB_SHAPES = [
  'circle',
  'squircle',
  'triangle',
  'cloud',
  'cylinder',
  'drop',
];

export const LOOK_DIRECTIONS = ['right', 'left', 'center', 'up', 'down'];

/**
 * Default sticker pile representing 6 playful companion bots.
 */
export const DEFAULT_BOT_PILE = [
  {
    id: 'bot-rusty',
    name: 'Rusty',
    shape: 'squircle',
    color: '#FF6B4A',
    size: 70,
    tilt: -18,
    lookDirection: 'right',
    status: 'idle',
  },
  {
    id: 'bot-volt',
    name: 'Volt',
    shape: 'circle',
    color: '#3B82F6',
    size: 85,
    tilt: 14,
    lookDirection: 'left',
    status: 'idle',
  },
  {
    id: 'bot-sunny',
    name: 'Sunny',
    shape: 'triangle',
    color: '#EAB308',
    size: 60,
    tilt: 24,
    lookDirection: 'up',
    status: 'idle',
  },
  {
    id: 'bot-nebula',
    name: 'Nebula',
    shape: 'drop',
    color: '#A855F7',
    size: 75,
    tilt: -8,
    lookDirection: 'right',
    status: 'idle',
  },
  {
    id: 'bot-sprout',
    name: 'Sprout',
    shape: 'cylinder',
    color: '#10B981',
    size: 55,
    tilt: 10,
    lookDirection: 'left',
    status: 'idle',
  },
  {
    id: 'bot-puff',
    name: 'Puff',
    shape: 'cloud',
    color: '#F43F5E',
    size: 65,
    tilt: -12,
    lookDirection: 'right',
    status: 'idle',
  },
];

/**
 * Pre-configured bot roles for agentic workflows
 */
export const ROLE_PRESETS = {
  assistant: {
    name: 'Assistant',
    shape: 'circle',
    color: '#FF5C35',
    tilt: 0,
    lookDirection: 'right',
  },
  coder: {
    name: 'Coder',
    shape: 'squircle',
    color: '#358BFF',
    tilt: -6,
    lookDirection: 'left',
  },
  architect: {
    name: 'Architect',
    shape: 'cylinder',
    color: '#9B51E0',
    tilt: 15,
    lookDirection: 'center',
  },
  reviewer: {
    name: 'Reviewer',
    shape: 'triangle',
    color: '#10B981',
    tilt: 8,
    lookDirection: 'up',
  },
  creative: {
    name: 'Creative',
    shape: 'cloud',
    color: '#FF76A5',
    tilt: -10,
    lookDirection: 'right',
  },
  explorer: {
    name: 'Explorer',
    shape: 'drop',
    color: '#FFC700',
    tilt: 12,
    lookDirection: 'up',
  },
};

/**
 * Returns a randomized cute blob configuration.
 */
export function getRandomBlob(overrides = {}) {
  const randomColor = BLOB_COLOR_LIST[Math.floor(Math.random() * BLOB_COLOR_LIST.length)];
  const randomShape = BLOB_SHAPES[Math.floor(Math.random() * BLOB_SHAPES.length)];
  const randomDirection = LOOK_DIRECTIONS[Math.floor(Math.random() * LOOK_DIRECTIONS.length)];
  const randomTilt = Math.floor(Math.random() * 32) - 16; // -16 to +16 deg

  return {
    shape: randomShape,
    color: randomColor,
    tilt: randomTilt,
    lookDirection: randomDirection,
    status: 'idle',
    size: 48,
    ...overrides,
  };
}

/**
 * Retrieve a preset configuration by role name.
 */
export function getBotByRole(role, overrides = {}) {
  const base = ROLE_PRESETS[role] || ROLE_PRESETS.assistant;
  return { ...base, ...overrides };
}
