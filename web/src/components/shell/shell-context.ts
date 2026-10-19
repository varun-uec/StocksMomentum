/**
 * What the workstation shell offers a route (plan 2026-10-19, D23): the route
 * slot in the header bar, where a route puts its own controls.
 */

import { createContext, useContext } from 'react';

export interface ShellApi {
  /** The header bar's route slot. Null until the shell has mounted. */
  routeSlot: HTMLElement | null;
}

export const ShellContext = createContext<ShellApi>({ routeSlot: null });

export function useShell(): ShellApi {
  return useContext(ShellContext);
}
