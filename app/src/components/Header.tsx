"use client";

import Link from "next/link";
import { useTide, TIDE_MODE } from "@/lib/tide";

// Roles the demo cares about; shown so each persona's power is visible on video.
const DEMO_ROLES = ["_tide_genome.selfencrypt", "_tide_genome.selfdecrypt"];

export default function Header() {
  const { authenticated, isInitializing, login, logout, getValueFromIdToken, hasRealmRole } = useTide();

  const username = authenticated ? getValueFromIdToken("preferred_username") : null;
  const roles = authenticated ? DEMO_ROLES.filter((r) => hasRealmRole(r)) : [];

  return (
    <header>
      <div className="banner">Synthetic data only. No real person or genome.</div>
      {TIDE_MODE === "simulated" && (
        <div className="banner sim">
          Simulated TideCloak: sign-in, roles, quorum approvals and the Fabric&apos;s access checks are mocked in this mode.
        </div>
      )}
      <nav>
        <strong>Unsellable</strong>
        <Link href="/">Home</Link>
        <Link href="/genome">My genome</Link>
        <Link href="/admin">Admin</Link>
        <Link href="/quorum">Quorum</Link>
        <Link href="/database">Database view</Link>
        <span className="spacer" />
        {isInitializing ? (
          <span>…</span>
        ) : authenticated ? (
          <>
            <span data-testid="user">
              {username} · roles: {roles.length ? roles.join(", ") : "none"}
            </span>
            <button onClick={() => logout()}>Log out</button>
          </>
        ) : (
          <button onClick={() => login()}>Log in</button>
        )}
      </nav>
    </header>
  );
}
