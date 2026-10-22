// Shared helpers for the simulated TideCloak API routes (/api/sim/*).
import { NextResponse } from "next/server";
import { SimError } from "./iga";

export const SIM_ENABLED = process.env.NEXT_PUBLIC_TIDE_MODE === "simulated";

// The simulated "access token" is just the signed-in persona's username, sent by the
// simulated provider in this header. Real TideCloak verifies a signed token instead.
export const actorOf = (req: Request) => req.headers.get("x-sim-user") ?? "";

export async function handle(fn: () => Promise<unknown>, okStatus = 200) {
  if (!SIM_ENABLED) return NextResponse.json({ error: "simulation disabled" }, { status: 404 });
  try {
    const body = await fn();
    return body === undefined ? new NextResponse(null, { status: 204 }) : NextResponse.json(body, { status: okStatus });
  } catch (e) {
    if (e instanceof SimError) return NextResponse.json({ error: e.message }, { status: e.status });
    return NextResponse.json({ error: String(e) }, { status: 500 });
  }
}
