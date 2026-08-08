import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { NavBar } from "@/components/shared/NavBar";
import { ThemeInitScript, ThemeProvider } from "./theme-provider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Momentum25 India",
  description: "Deterministic, explainable momentum-stock screener for the Indian market.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.className} suppressHydrationWarning>
      <head>
        <ThemeInitScript />
      </head>
      <body className="bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 transition-colors">
        <ThemeProvider>
          <Providers>
            <NavBar />
            {children}
          </Providers>
        </ThemeProvider>
      </body>
    </html>
  );
}