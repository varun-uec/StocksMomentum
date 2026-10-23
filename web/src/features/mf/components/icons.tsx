/** Stroke icons for the MF workstation: 24-unit grid, `currentColor`, hidden from assistive tech. */
import type { ReactNode } from 'react';

function icon(paths: ReactNode) {
  return function Icon({ className = 'h-[18px] w-[18px]' }: { className?: string }) {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
        {paths}
      </svg>
    );
  };
}

export const I = {
  discover: icon(<><circle cx="12" cy="12" r="9" /><path d="m15.5 8.5-2 5-5 2 2-5z" /></>),
  screen: icon(<path d="M4 5h16l-6 7.5V19l-4-2v-4.5z" />),
  studio: icon(<><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></>),
  compare: icon(<><rect x="3" y="4" width="7" height="16" rx="1.5" /><rect x="14" y="4" width="7" height="16" rx="1.5" /></>),
  lab: icon(<><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M8 7h8M8 11h2M12 11h2M16 11h0M8 15h2M12 15h2M8 18h2M12 18h4" /></>),
  portfolio: icon(<><path d="M12 3a9 9 0 1 0 9 9h-9z" /><path d="M15 3.5A9 9 0 0 1 20.5 9H15z" /></>),
  ask: icon(<><path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6z" /><path d="M18.5 15l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z" /></>),
  star: icon(<path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z" />),
  bookmark: icon(<path d="M6 3h12v18l-6-4-6 4z" />),
  note: icon(<><path d="M5 3h10l4 4v14H5z" /><path d="M15 3v4h4M8 12h8M8 16h5" /></>),
  bell: icon(<><path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" /><path d="M10 20a2 2 0 0 0 4 0" /></>),
  search: icon(<><circle cx="11" cy="11" r="6.5" /><path d="m20 20-4.2-4.2" /></>),
  sun: icon(<><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>),
  moon: icon(<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />),
  plus: icon(<path d="M12 5v14M5 12h14" />),
  x: icon(<path d="M6 6l12 12M18 6 6 18" />),
  check: icon(<path d="m5 12.5 4.5 4.5L19 7.5" />),
  chevronRight: icon(<path d="m9 6 6 6-6 6" />),
  chevronDown: icon(<path d="m6 9 6 6 6-6" />),
  arrowLeft: icon(<path d="M19 12H5M11 18l-6-6 6-6" />),
  arrowUpRight: icon(<path d="M7 17 17 7M8 7h9v9" />),
  download: icon(<path d="M12 4v11M7 10l5 5 5-5M5 20h14" />),
  info: icon(<><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h0" /></>),
  menu: icon(<path d="M4 7h16M4 12h16M4 17h16" />),
  more: icon(<><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></>),
  layers: icon(<><path d="m12 3 9 5-9 5-9-5z" /><path d="m3 13 9 5 9-5" /></>),
  trend: icon(<><path d="M3 17l6-6 4 4 8-8" /><path d="M15 7h6v6" /></>),
  shield: icon(<path d="M12 3 5 6v6c0 4.2 3 7.6 7 9 4-1.4 7-4.8 7-9V6z" />),
  calendar: icon(<><rect x="3.5" y="5" width="17" height="15" rx="2" /><path d="M3.5 10h17M8 3v4M16 3v4" /></>),
  stocks: icon(<><path d="M7 4v16M17 4v16" /><rect x="4.5" y="8" width="5" height="7" rx="1" /><rect x="14.5" y="6" width="5" height="9" rx="1" /></>),
  settings: icon(<><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M4.9 4.9 7 7M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1" /></>),
  grid: icon(<><rect x="4" y="4" width="7" height="7" rx="1" /><rect x="13" y="4" width="7" height="7" rx="1" /><rect x="4" y="13" width="7" height="7" rx="1" /><rect x="13" y="13" width="7" height="7" rx="1" /></>),
  list: icon(<path d="M8 6h12M8 12h12M8 18h12M4 6h0M4 12h0M4 18h0" />),
};
