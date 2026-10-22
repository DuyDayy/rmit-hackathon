"use client";

// Simulated TideCloak sign-in: pick a persona. With real TideCloak this is the Tide enclave
// login (BYOiD), and no password is stored by the app or TideCloak.
// /sim-login?as=<persona>&next=<path> signs in directly (used by `npm run demo` to open one tab per persona).
import { useEffect } from "react";
import { PERSONAS, findPersona } from "@/lib/sim/personas";
import { simSignIn } from "@/lib/sim/SimTideCloakProvider";
import { TIDE_MODE } from "@/lib/tide";

const go = (username: string) => {
  simSignIn(username);
  const next = new URLSearchParams(window.location.search).get("next") || "/";
  window.location.assign(next.startsWith("/") ? next : "/");
};

export default function SimLogin() {
  useEffect(() => {
    if (TIDE_MODE !== "simulated") return;
    const as = new URLSearchParams(window.location.search).get("as");
    if (as && findPersona(as)) go(as);
  }, []);

  if (TIDE_MODE !== "simulated") return <p>Simulated sign-in is off. Run <code>npm run dev:sim</code>.</p>;

  return (
    <>
      <h1>Sign in (simulated TideCloak)</h1>
      <p>
        Choose a persona. Each browser tab keeps its own session, so you can open one tab per persona.
      </p>
      <div className="personas">
        {PERSONAS.map((p) => (
          <div key={p.username} className="persona">
            <strong>{p.displayName}</strong>
            <p>{p.story}</p>
            <button onClick={() => go(p.username)}>{p.username}</button>
          </div>
        ))}
      </div>
    </>
  );
}
