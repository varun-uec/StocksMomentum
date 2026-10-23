import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            // A 4xx is the server's final answer: retrying only delays the error.
            retry: (failures, error) => {
              const status = (error as { status?: unknown }).status;
              return failures < 1 && !(typeof status === 'number' && status < 500);
            },
            // Refocusing the window must not refetch and reflow a table the
            // reader is part-way through scrolling.
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}