"use client";

// Simulated TideCloak sign-in: pick a persona. With real TideCloak this is the Tide enclave
// login (BYOiD), and no password is stored by the app or TideCloak.
import { PERSONAS } from "@/lib/sim/personas";
import { simSignIn } from "@/lib/sim/SimTideCloakProvider";
import { TIDE_MODE } from "@/lib/tide";

export default function SimLogin() {
  if (TIDE_MODE !== "simulated") return <p>Simulated sign-in is off. Run <code>npm run dev:sim</code>.</p>;

  const signIn = (username: string) => {
    simSignIn(username);
    const next = new URLSearchParams(window.location.search).get("next") || "/";
    window.location.assign(next.startsWith("/") ? next : "/");
  };

  return (
    <>
      <h1>Sign in (simulated TideCloak)</h1>
      <p>
        Choose a persona. Each browser tab keeps its own session, so you can open one tab per persona.
      </p>
      <table>
        <tbody>
          {PERSONAS.map((p) => (
            <tr key={p.username}>
              <td>
                <button onClick={() => signIn(p.username)}>{p.username}</button>
              </td>
              <td>
                <strong>{p.displayName}</strong>
                <br />
                {p.story}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
