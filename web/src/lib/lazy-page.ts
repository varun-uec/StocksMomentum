import type { ComponentType } from 'react';
import type { RouteObject } from 'react-router';

type PageModule = { default: ComponentType };

/** One code-split chunk per route, as the Next.js build had. */
export function page(load: () => Promise<PageModule>): Pick<RouteObject, 'lazy'> {
  return { lazy: async () => ({ Component: (await load()).default }) };
}
