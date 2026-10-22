"use client";

import { useEffect, useState } from "react";
import { TideCloakContextProvider } from "@tidecloak/nextjs";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/adapter")
      .then(async (r) => (r.ok ? setConfig(await r.json()) : setError((await r.json()).error)))
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <p className="denied">TideCloak not configured: {error}</p>;
  if (!config) return <p>Loading TideCloak config…</p>;
  return <TideCloakContextProvider config={config}>{children}</TideCloakContextProvider>;
}
