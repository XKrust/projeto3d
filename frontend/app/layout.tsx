import type { Metadata } from "next";
import { Suspense } from "react";
import { Bricolage_Grotesque, Geist, Geist_Mono } from "next/font/google";
import { Nav } from "@/components/Nav";
import "./globals.css";

// Títulos e números grandes — ver design.md (tipografia).
const bricolage = Bricolage_Grotesque({
  variable: "--font-bricolage",
  subsets: ["latin"],
  display: "swap",
});

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Radar 3D",
  description: "Radar de tendências para modeladores 3D",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="pt-BR"
      className={`${bricolage.variable} ${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <Suspense fallback={null}>
          <Nav />
        </Suspense>
        <main className="flex flex-1 flex-col pt-24 sm:pt-28">{children}</main>
        <footer className="mx-auto w-full max-w-6xl px-4 pb-8 pt-16 sm:px-8">
          <p className="border-t border-border pt-4 text-sm text-muted-foreground">
            Radar 3D · roda só no seu computador · notas de oportunidade, chance
            de venda e preço são estimativas
          </p>
        </footer>
      </body>
    </html>
  );
}
