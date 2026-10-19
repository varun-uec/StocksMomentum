/**
 * What the workstation shell offers a route (plan 2026-10-19, D23): the route
 * slot in the header bar, where a route puts its own controls, and the right
 * panel, which shows the route's context.
 */

import { createContext, useContext, useEffect } from 'react';
import type { PanelTab } from '@/components/workspace/SidePanel';
import type { EvidenceControl } from '@/components/momentum25/evidence';

/** What the right panel is about on the current route. */
export interface PanelContext {
  /** The symbol the route is about. Without one, Details hides and Alerts lists only. */
  symbol?: string;
  /** Show the Details (Assessment) tab for the symbol. Symbol pages are the assessment. */
  assessment?: boolean;
  /** Use the panel state saved with the workspace (/chart). Other routes start closed. */
  saved?: boolean;
  /** Allow the panel inline beside the content on wide screens; else it overlays. */
  inline?: boolean;
  /** The route's run in view (a historical screener); Assessment uses the latest run when absent. */
  runId?: number;
  /** The page's "Show on chart" layers for the active chart (/chart). */
  evidence?: EvidenceControl;
  /** Show the Object tree tab: the active chart fills `objectsSlot` (/chart). */
  objects?: boolean;
}

export interface ShellApi {
  /** The header bar's route slot. Null until the shell has mounted. */
  routeSlot: HTMLElement | null;
  /** The Object tree tab's body while it is open; the active chart portals its drawings list into it. */
  objectsSlot: HTMLElement | null;
  setPanelContext: (context: PanelContext) => void;
  /** Open a panel tab; `alertPrice` prefills a new alert. */
  openPanel: (tab: PanelTab, alertPrice?: number) => void;
}

export const ShellContext = createContext<ShellApi>({ routeSlot: null, objectsSlot: null, setPanelContext: () => {}, openPanel: () => {} });

export function useShell(): ShellApi {
  return useContext(ShellContext);
}

/** Declare the route's panel context while the route is mounted. */
export function useShellPanel({ symbol, assessment, saved, inline, objects, runId, evidence }: PanelContext): void {
  const { setPanelContext } = useShell();
  useEffect(() => {
    setPanelContext({ symbol, assessment, saved, inline, objects, runId, evidence });
    return () => setPanelContext({});
  }, [setPanelContext, symbol, assessment, saved, inline, objects, runId, evidence]);
}
