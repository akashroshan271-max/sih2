import type { Metadata } from "next";

import { LoginView } from "@/components/auth/login-view";

export const metadata: Metadata = {
  title: "Officer sign-in",
};

export default function LoginPage() {
  return <LoginView />;
}
