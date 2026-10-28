import { AppShell } from "@/components/shell/app-shell";

export default function ConsoleLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return <AppShell>{children}</AppShell>;
}
