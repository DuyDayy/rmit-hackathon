"use client";

// Simulated TideCloak provider. Exposes the subset of useTideCloak() (@tidecloak/nextjs 0.14.40)
// that this app uses, so pages run unchanged against the simulation or the real SDK.
// Sign-in is a persona picker (/sim-login); the signed-in persona is kept per browser tab.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { REALM } from "./personas";
import { simDecrypt, simEncrypt } from "./fabric";
import type { TideLike } from "../tide-types";

const SESSION_KEY = "unsellable.sim.user";

type Claims = {
  sub: string;
  preferred_username: string;
  name: string;
  realm_access: { roles: string[] };
  resource_access: Record<string, { roles: string[] }>;
};

const SimContext = createContext<TideLike | null>(null);

async function simFetch(user: string, url: string, init: RequestInit = {}) {
  const res = await fetch(url, {
    ...init,
    headers: { "content-type": "application/json", "x-sim-user": user, ...(init.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${(await res.text().catch(() => "")) || res.statusText}`);
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

export function SimTideCloakProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<string | null>(null);
  const [claims, setClaims] = useState<Claims | null>(null);
  const [isInitializing, setInitializing] = useState(true);

  const loadClaims = useCallback(async (u: string) => {
    const c: Claims = await simFetch(u, `/api/sim/token/${encodeURIComponent(u)}`);
    setClaims(c);
    return c;
  }, []);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = sessionStorage.getItem(SESSION_KEY);
    } catch {}
    if (!stored) {
      setInitializing(false);
      return;
    }
    setUser(stored);
    loadClaims(stored)
      .catch(() => setUser(null))
      .finally(() => setInitializing(false));
  }, [loadClaims]);

  const value = useMemo<TideLike>(() => {
    const requireUser = () => {
      if (!user) throw new Error("Not signed in");
      return user;
    };
    // Like a token refresh: re-read roles so quorum-committed grants take effect.
    const freshRoles = async () => (await loadClaims(requireUser())).realm_access.roles;

    return {
      isInitializing,
      authenticated: !!user && !!claims,
      login: async () => {
        window.location.assign(`/sim-login?next=${encodeURIComponent(window.location.pathname)}`);
      },
      logout: async () => {
        try {
          sessionStorage.removeItem(SESSION_KEY);
        } catch {}
        window.location.assign("/");
      },
      getValueFromToken: (key: string) => (claims as Record<string, unknown> | null)?.[key],
      getValueFromIdToken: (key: string) => (claims as Record<string, unknown> | null)?.[key],
      hasRealmRole: (role: string) => !!claims?.realm_access.roles.includes(role),
      doEncrypt: async (items) => simEncrypt(items, requireUser(), await freshRoles()),
      doDecrypt: async (items) => simDecrypt(items, requireUser(), await freshRoles()),
      AdminAPI: {
        getRealm: () => REALM,
        getRole: async (name: string) => ({ name }),
        getUserRoles: (userId: string) => simFetch(requireUser(), `/api/sim/users/${encodeURIComponent(userId)}/roles`),
        addUserRoles: (userId: string, roles: { name: string }[]) =>
          simFetch(requireUser(), `/api/sim/users/${encodeURIComponent(userId)}/roles`, { method: "POST", body: JSON.stringify(roles) }),
        // Only the IGA change-request inbox is simulated.
        fetch: (endpoint: string, init?: RequestInit) => {
          const m = endpoint.match(/\/iga\/change-requests(\/[^?]+)?(\?.*)?$/);
          if (!m) throw new Error(`Simulated AdminAPI: ${endpoint} is not simulated`);
          return simFetch(requireUser(), `/api/sim/change-requests${m[1] ?? ""}${m[2] ?? ""}`, init);
        },
      },
    };
  }, [user, claims, isInitializing, loadClaims]);

  return <SimContext.Provider value={value}>{children}</SimContext.Provider>;
}

export function useSimTideCloak(): TideLike {
  const ctx = useContext(SimContext);
  if (!ctx) throw new Error("useSimTideCloak outside SimTideCloakProvider");
  return ctx;
}

export const simSignIn = (username: string) => {
  try {
    sessionStorage.setItem(SESSION_KEY, username);
  } catch {}
};
