import { NextResponse } from "next/server";
import { readAll } from "@/lib/db";

// C4: anyone can download the whole store. It proves exporting the file gets you ciphertext only.
export const dynamic = "force-dynamic";

export async function GET() {
  return new NextResponse(JSON.stringify(await readAll(), null, 2), {
    headers: {
      "content-type": "application/json",
      "content-disposition": 'attachment; filename="unsellable-export.json"',
    },
  });
}
