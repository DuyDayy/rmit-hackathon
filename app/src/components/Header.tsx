"use client";

import { useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTide, TIDE_MODE } from "@/lib/tide";

// Roles the demo cares about; shown so each persona's power is visible on video.
const DEMO_ROLES = ["_tide_genome.selfencrypt", "_tide_genome.selfdecrypt"];

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/genome", label: "My genome" },
  { href: "/admin", label: "Admin" },
  { href: "/quorum", label: "Quorum" },
  { href: "/database", label: "Database view" },
];

export default function Header() {
  const { authenticated, isInitializing, login, logout, getValueFromIdToken, hasRealmRole } = useTide();
  const pathname = usePathname();

  const username = authenticated ? getValueFromIdToken("preferred_username") : null;
  const roles = authenticated ? DEMO_ROLES.filter((r) => hasRealmRole(r)) : [];

  // Name the browser tab after the signed-in persona, so each tab is easy to find while demoing.
  useEffect(() => {
    document.title = username ? `${username} · Unsellable` : "Unsellable";
  });

  return (
    <header>
      <div className="banner">Synthetic data only. No real person or genome.</div>
      {TIDE_MODE === "simulated" && (
        <div className="banner sim">
          Simulated TideCloak: sign-in, roles, quorum approvals and the Fabric&apos;s access checks are mocked in this mode.
        </div>
      )}
      <nav>
        <Link href="/" className="brand">
          <span className="mark">🧬</span>Unsellable
        </Link>
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} className={`navlink${pathname === l.href ? " active" : ""}`}>
            {l.label}
          </Link>
        ))}
        <span className="spacer" />
        {isInitializing ? (
          <span className="who">…</span>
        ) : authenticated ? (
          <>
            <span data-testid="user" className="who">
              <span className="name">{username}</span> · roles:{" "}
              {roles.length ? (
                roles.map((r) => (
                  <span key={r} className="badge">
                    {r}
                  </span>
                ))
              ) : (
                <span className="badge none">none</span>
              )}
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
