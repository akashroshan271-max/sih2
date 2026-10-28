"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { homeForRole } from "@/lib/constants";

export default function HomePage() {
  const { officer, status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated" && officer) {
      router.replace(homeForRole(officer.role));
    }
  }, [status, officer, router]);

  return (
    <p className="py-16 text-sm text-ink-soft" role="status">
      Opening your desk…
    </p>
  );
}
