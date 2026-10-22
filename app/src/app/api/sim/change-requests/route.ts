import { listChangeRequests } from "@/lib/sim/iga";
import { actorOf, handle } from "@/lib/sim/route";

export const dynamic = "force-dynamic";

// Mirrors GET /admin/realms/{realm}/iga/change-requests?status=PENDING
export async function GET(req: Request) {
  const status = new URL(req.url).searchParams.get("status") ?? undefined;
  return handle(() => listChangeRequests(actorOf(req), status));
}
