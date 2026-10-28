import type { Metadata } from "next";

import { AuthProvider } from "@/components/auth/auth-provider";
import { Providers } from "@/components/providers";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "VERIFLOW · AICTE approval command centre",
    template: "%s · VERIFLOW",
  },
  description:
    "Verification flow and compliance control for AICTE technical institutions under APH 2024-27.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-IN">
      <body>
        <Providers>
          <AuthProvider>{children}</AuthProvider>
        </Providers>
      </body>
    </html>
  );
}
