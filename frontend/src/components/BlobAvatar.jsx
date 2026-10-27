import React from 'react';
import { motion } from 'framer-motion';
import { DEFAULT_BOT_PILE } from './blobPresets.js';

/**
 * Returns the base center coordinate (cx, cy) for the eyes in a 100x100 viewBox
 * depending on the blob shape geometry.
 */
function getBaseEyePosition(shape) {
  switch (shape) {
    case 'drop':
      // The drop is fat on bottom-left and tapers to top-right
      return { x: 38, y: 58 };
    case 'triangle':
      // Triangle narrows at the apex; center-belly is slightly lower
      return { x: 50, y: 50 };
    case 'cylinder':
      return { x: 52, y: 46 };
    case 'cloud':
    case 'squircle':
    case 'circle':
    default:
      // Iconic slightly off-center Grok mascot placement
      return { x: 55, y: 45 };
  }
}

/**
 * Directional offsets for where the eyes look.
 */
const LOOK_OFFSETS = {
  right: { x: 5, y: 0 },
  left: { x: -5, y: 0 },
  up: { x: 0, y: -4 },
  down: { x: 0, y: 4 },
  center: { x: 0, y: 0 },
};

/**
 * Renders the SVG shape path based on the shape prop.
 */
function BlobShape({ shape, color }) {
  switch (shape) {
    case 'squircle':
      return (
        <rect
          x="8"
          y="8"
          width="84"
          height="84"
          rx="28"
          fill={color}
        />
      );

    case 'triangle':
      return (
        <path
          d="M50 10 C62 10, 90 68, 86 82 C82 94, 18 94, 14 82 C10 68, 38 10, 50 10 Z"
          fill={color}
        />
      );

    case 'cloud':
      return (
        <path
          d="M 81.2 32.0 A 22 22 0 0 1 81.2 68.0 A 22 22 0 0 1 50.0 86.0 A 22 22 0 0 1 18.8 68.0 A 22 22 0 0 1 18.8 32.0 A 22 22 0 0 1 50.0 14.0 A 22 22 0 0 1 81.2 32.0 Z"
          fill={color}
        />
      );

    case 'cylinder':
      return (
        <rect
          x="14"
          y="10"
          width="72"
          height="80"
          rx="22"
          fill={color}
        />
      );

    case 'drop':
      return (
        <path
          d="M 76 16 C 82 22, 88 44, 84 64 C 80 80, 64 90, 44 90 C 24 90, 12 78, 12 58 C 12 38, 28 22, 52 14 C 64 10, 72 12, 76 16 Z"
          fill={color}
        />
      );

    case 'circle':
    default:
      return (
        <circle
          cx="50"
          cy="50"
          r="44"
          fill={color}
        />
      );
  }
}

/**
 * BlobAvatar Component
 * Playful, animated vector mascot inspired by Grok.
 */
export function BlobAvatar({
  shape = 'circle',
  color = '#FF5C35',
  size = 40,
  status = 'idle',
  tilt = 0,
  lookDirection = 'right',
  className = '',
  onClick,
}) {
  // Base tilt compensation (cylinders lean 15 deg by default)
  const effectiveTilt = (Number(tilt) || 0) + (shape === 'cylinder' ? 15 : 0);

  // Look direction & eye coordinates calculation
  const baseEye = getBaseEyePosition(shape);
  const lookOffset = LOOK_OFFSETS[lookDirection] || LOOK_OFFSETS.right;
  const targetEyeX = baseEye.x + lookOffset.x;
  const targetEyeY = baseEye.y + lookOffset.y;

  // Active status checks
  const isBusy = status === 'working' || status === 'typing';
  const isDone = status === 'done';

  // Dimension formatting (handles numbers, px, rem, or Tailwind classes)
  const numericSize =
    typeof size === 'number'
      ? size
      : !isNaN(Number(size))
      ? Number(size)
      : null;

  const styleDimension =
    numericSize !== null
      ? { width: `${numericSize}px`, height: `${numericSize}px` }
      : typeof size === 'string' && /px|rem|em|%|vw|vh/.test(size)
      ? { width: size, height: size }
      : undefined;

  // Animation variants for the outer body group
  const bodyAnimation = isBusy
    ? {
        rotate: [effectiveTilt - 5, effectiveTilt + 5, effectiveTilt - 5],
        y: [0, -1.5, 0],
      }
    : isDone
    ? {
        rotate: [effectiveTilt, effectiveTilt - 4, effectiveTilt + 4, effectiveTilt],
        scale: [1, 1.08, 0.96, 1],
        y: [0, -5, 1, 0],
      }
    : {
        rotate: effectiveTilt,
        y: [0, -1.5, 0],
      };

  const bodyTransition = isBusy
    ? {
        repeat: Infinity,
        duration: 1.2,
        ease: 'easeInOut',
      }
    : isDone
    ? {
        duration: 0.6,
        ease: 'easeOut',
      }
    : {
        repeat: Infinity,
        duration: 3.5,
        ease: 'easeInOut',
      };

  // Eyes animation (curious scanning left/right when busy)
  const eyeGroupAnimation = isBusy
    ? {
        x: [targetEyeX - 4, targetEyeX + 5, targetEyeX - 2, targetEyeX],
        y: targetEyeY,
      }
    : {
        x: targetEyeX,
        y: targetEyeY,
      };

  const eyeGroupTransition = isBusy
    ? {
        repeat: Infinity,
        duration: 1.6,
        ease: 'easeInOut',
      }
    : {
        type: 'spring',
        stiffness: 280,
        damping: 20,
      };

  return (
    <motion.svg
      viewBox="0 0 100 100"
      width={numericSize || undefined}
      height={numericSize || undefined}
      style={styleDimension}
      className={`inline-block select-none overflow-visible filter drop-shadow-[0_4px_8px_rgba(0,0,0,0.12)] ${
        onClick ? 'cursor-pointer' : ''
      } ${className}`}
      onClick={onClick}
      whileHover={onClick ? { scale: 1.08 } : undefined}
      whileTap={onClick ? { scale: 0.94 } : undefined}
      role="img"
      aria-label={`${shape} mascot in ${status} status`}
    >
      {/* Animated Body Group */}
      <motion.g
        style={{ transformOrigin: '50px 50px' }}
        animate={bodyAnimation}
        transition={bodyTransition}
      >
        {/* Vector Mascot Silhouette */}
        <BlobShape shape={shape} color={color} />

        {/* Eye Cluster Group */}
        <motion.g
          animate={eyeGroupAnimation}
          transition={eyeGroupTransition}
        >
          {/* Natural Grok Pill Angle (-11deg) */}
          <g transform="rotate(-11)">
            {/* Periodic Blink Animation Container */}
            <motion.g
              animate={{ scaleY: [1, 0.08, 1] }}
              transition={{
                duration: 0.18,
                times: [0, 0.5, 1],
                repeat: Infinity,
                repeatDelay: 3.5,
                ease: 'easeInOut',
              }}
              style={{ transformOrigin: '0px 0px' }}
            >
              {/* Left Eye Pill */}
              <rect
                x="-11.5"
                y="-11"
                width="9"
                height="22"
                rx="4.5"
                fill="#FFFFFF"
              />
              {/* Right Eye Pill */}
              <rect
                x="2.5"
                y="-11"
                width="9"
                height="22"
                rx="4.5"
                fill="#FFFFFF"
              />
            </motion.g>
          </g>
        </motion.g>
      </motion.g>
    </motion.svg>
  );
}

/**
 * BotPile Component
 * Stacks a playful pile/cluster of Grok companion bots overlapping like stickers.
 */
export function BotPile({
  bots = DEFAULT_BOT_PILE,
  className = '',
  onBotClick,
}) {
  const botList = bots && bots.length > 0 ? bots : DEFAULT_BOT_PILE;

  return (
    <div
      className={`relative inline-flex items-end justify-center select-none -space-x-4 sm:-space-x-5 py-3 px-2 ${className}`}
    >
      {botList.map((bot, index) => {
        const isInteractive = Boolean(onBotClick);
        return (
          <motion.div
            key={bot.id || `bot-pile-${index}`}
            className={`relative transition-transform ${
              isInteractive ? 'cursor-pointer' : ''
            }`}
            style={{ zIndex: index + 1 }}
            whileHover={{
              y: -8,
              scale: 1.14,
              zIndex: 40,
              transition: { type: 'spring', stiffness: 350, damping: 18 },
            }}
            whileTap={isInteractive ? { scale: 0.94 } : undefined}
            onClick={() => onBotClick?.(bot, index)}
          >
            <BlobAvatar
              shape={bot.shape}
              color={bot.color}
              size={bot.size}
              tilt={bot.tilt}
              lookDirection={bot.lookDirection}
              status={bot.status || 'idle'}
              className="drop-shadow-md"
            />
          </motion.div>
        );
      })}
    </div>
  );
}

export default BlobAvatar;
