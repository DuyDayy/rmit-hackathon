import { NextResponse } from "next/server";
import { readAll, upsert } from "@/lib/db";

// GET /api/genome -> every stored record (ciphertext only). Used by Export all and Database view.
export async function GET() {
  return NextResponse.json(await readAll());
}

// POST /api/genome -> store one sealed record.
export async function POST(req: Request) {
  const body = await req.json();
  if (typeof body?.participantId !== "string" || typeof body?.genome !== "string") {
    return NextResponse.json({ error: "participantId and genome (ciphertext string) required" }, { status: 400 });
  }
  const record = {
    participantId: body.participantId,
    displayName: body.displayName ?? body.participantId,
    consent: body.consent ?? { cancerResearch: false, commercialAiTraining: false },
    genome: body.genome,
    updatedAt: new Date().toISOString(),
  };
  await upsert(record);
  return NextResponse.json(record, { status: 201 });
}
