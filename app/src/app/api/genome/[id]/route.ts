import { NextResponse } from "next/server";
import { readAll } from "@/lib/db";

// GET /api/genome/:id -> one record's ciphertext.
export async function GET(_req: Request, { params }: { params: { id: string } }) {
  const record = (await readAll()).find((r) => r.participantId === params.id);
  return record ? NextResponse.json(record) : NextResponse.json({ error: "not found" }, { status: 404 });
}
