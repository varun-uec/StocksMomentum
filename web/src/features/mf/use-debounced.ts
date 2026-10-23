import { useEffect, useState } from 'react';

/** `value`, once it has stayed the same for `ms`. Pass a primitive: an object changes every render. */
export function useDebounced<T extends string | number>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}
