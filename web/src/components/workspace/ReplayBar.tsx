/**
 * Bar replay controls (plan B2): the replay date, step, play and speed, and
 * exit. The page owns the state; every chart on it reads the same date.
 */

import { useEffect } from 'react';
import { isTyping } from '@/lib/shortcuts';
import { focusRing } from '@/lib/theme';
import { nextSession, sessionOnOrBefore } from '@/lib/replay';

export const REPLAY_SPEEDS = { '1×': 1000, '3×': 333, '10×': 100 } as const;
export type ReplaySpeed = keyof typeof REPLAY_SPEEDS;

export interface Replay {
  date: string;
  playing: boolean;
  speed: ReplaySpeed;
}

const btn = `h-7 px-2 inline-flex items-center gap-1 rounded-md text-xs font-medium border border-[var(--ws-line)] hover:bg-[var(--ws-muted)] disabled:opacity-50 ${focusRing}`;

export function ReplayBar({
  replay,
  sessions,
  loading,
  onChange,
  onExit,
}: {
  replay: Replay;
  /** The active chart's stored daily sessions: where a step can land. */
  sessions: string[];
  /** The step's series are still loading; play waits for them. */
  loading: boolean;
  onChange: (next: Replay) => void;
  onExit: () => void;
}) {
  const next = nextSession(sessions, replay.date);
  const step = () => next && onChange({ ...replay, date: next });

  // Shift+→ steps one session, as in TradingView's replay.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (!e.shiftKey || e.key !== 'ArrowRight' || isTyping(e) || !next) return;
      e.preventDefault();
      onChange({ ...replay, date: next, playing: false });
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [replay, next, onChange]);

  // Play steps once the previous step's bars have arrived, so a slow fetch never queues steps.
  useEffect(() => {
    if (!replay.playing || loading) return;
    const timer = setTimeout(() => onChange(next ? { ...replay, date: next } : { ...replay, playing: false }), REPLAY_SPEEDS[replay.speed]);
    return () => clearTimeout(timer);
  }, [replay, loading, next, onChange]);

  return (
    <div role="toolbar" aria-label="Bar replay" className="chart-replay">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--ws-accent)]">Replay</span>
      <label className="flex items-center gap-1 text-xs">
        <span className="sr-only">Replay date</span>
        <input
          type="date"
          aria-label="Replay date"
          value={replay.date}
          min={sessions[0]}
          max={sessions.at(-2)}
          onChange={(e) => {
            const date = e.target.value && sessionOnOrBefore(sessions, e.target.value);
            if (date) onChange({ ...replay, date, playing: false });
          }}
          className={`h-7 px-1.5 rounded-md border border-[var(--ws-line)] bg-white dark:bg-slate-900 text-xs tabular-nums ${focusRing}`}
        />
      </label>
      <button type="button" onClick={() => onChange({ ...replay, playing: !replay.playing })} disabled={!next} aria-pressed={replay.playing} className={btn}>
        <span aria-hidden="true">{replay.playing ? '❚❚' : '▶'}</span>
        {replay.playing ? 'Pause' : 'Play'}
      </button>
      <button type="button" onClick={step} disabled={!next} title="Step forward one session (Shift+→)" aria-keyshortcuts="Shift+ArrowRight" className={btn}>
        <span aria-hidden="true">⏭</span>Step forward
      </button>
      <div role="group" aria-label="Replay speed" className="flex items-center gap-0.5">
        {(Object.keys(REPLAY_SPEEDS) as ReplaySpeed[]).map((speed) => (
          <button key={speed} type="button" aria-pressed={replay.speed === speed} onClick={() => onChange({ ...replay, speed })} className={`h-7 px-1.5 rounded text-xs tabular-nums ${focusRing} ${replay.speed === speed ? 'bg-[var(--ws-muted)] font-semibold' : 'text-slate-500 hover:bg-[var(--ws-muted)]'}`}>
            {speed}
          </button>
        ))}
      </div>
      <p role="status" className="text-[11px] text-slate-500 min-w-0 truncate order-last sm:order-none">
        {next ? `Bars, studies and drawings stop at ${replay.date}. Alerts are paused.` : `${replay.date} is the last stored session.`}
      </p>
      <button type="button" onClick={onExit} className={`${btn} ml-auto`}>
        Exit replay
      </button>
    </div>
  );
}
