/** The Discover hero's landscape: layered hills and pines in theme colours. Decorative only. */
import { token } from '../theme/themes';

const PINES: [number, number, number][] = [
  [455, 128, 1],
  [478, 120, 1.25],
  [502, 132, 0.9],
  [528, 112, 1.45],
  [556, 126, 1.05],
  [584, 118, 1.3],
  [610, 134, 0.85],
];

function Pine({ x, y, s }: { x: number; y: number; s: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <path d="M0 -46 L13 -14 L7 -14 L17 6 L-17 6 L-7 -14 L-13 -14 Z" fill={token('brand', 0.62)} />
      <rect x="-1.6" y="6" width="3.2" height="7" fill={token('brandStrong', 0.6)} />
    </g>
  );
}

export function HeroArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 640 200" preserveAspectRatio="xMaxYMax slice" className={className} aria-hidden="true">
      <defs>
        <linearGradient id="mf-hero-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={token('heroFrom')} />
          <stop offset="100%" stopColor={token('heroTo')} />
        </linearGradient>
      </defs>
      <rect width="640" height="200" fill="url(#mf-hero-sky)" />
      <circle cx="520" cy="46" r="20" fill={token('warning', 0.12)} />
      <path d="M180 150 C260 70 330 92 390 64 C450 36 520 70 640 42 L640 200 L180 200 Z" fill={token('brandAlt', 0.12)} />
      <path d="M250 168 C330 112 400 128 470 96 C540 64 590 100 640 84 L640 200 L250 200 Z" fill={token('brandAlt', 0.2)} />
      <path d="M320 186 C390 150 460 160 520 140 C570 124 610 138 640 132 L640 200 L320 200 Z" fill={token('brand', 0.18)} />
      {PINES.map(([x, y, s]) => (
        <Pine key={x} x={x} y={y + 20} s={s} />
      ))}
      <path d="M300 200 C380 178 470 182 640 168 L640 200 Z" fill={token('brand', 0.24)} />
    </svg>
  );
}
