import { NextResponse } from "next/server";
import { decide } from "@/lib/sim/iga";
import { actorOf, handle } from "@/lib/sim/route";

export const dynamic = "force-dynamic";

// Mirrors POST /admin/realms/{realm}/iga/change-requests/{id}/approve (and a reject decision).
export async function POST(req: Request, { params }: { params: { id: string; decision: string } }) {
  if (params.decision !== "approve" && params.decision !== "reject") {
    return NextResponse.json({ error: "decision must be approve or reject" }, { status: 400 });
  }
  return handle(() => decide(actorOf(req), params.id, params.decision as "approve" | "reject"));
}
