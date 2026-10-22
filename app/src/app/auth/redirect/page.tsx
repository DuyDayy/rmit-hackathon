"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTideCloak } from "@tidecloak/nextjs";

// Login callback target, as in the TideCloak Next.js front-channel guide.
export default function RedirectPage() {
  const { isInitializing } = useTideCloak();
  const router = useRouter();

  useEffect(() => {
    if (!isInitializing) router.push("/");
  }, [isInitializing, router]);

  return <p>Loading...</p>;
}
