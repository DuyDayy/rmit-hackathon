import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";

// Serves the TideCloak client adapter (A6 output) from app/tidecloak.json at runtime,
// so the app builds before the realm exists and fails loudly instead of silently.
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const raw = await fs.readFile(path.resolve(process.cwd(), "tidecloak.json"), "utf8");
    return new NextResponse(raw, { headers: { "content-type": "application/json" } });
  } catch {
    return NextResponse.json({ error: "app/tidecloak.json missing: export the client adapter from TideCloak (task A6)" }, { status: 503 });
  }
}
