import { requestGrant, userRealmRoles } from "@/lib/sim/iga";
import { actorOf, handle } from "@/lib/sim/route";

export const dynamic = "force-dynamic";

// Mirrors GET/POST /admin/realms/{realm}/users/{id}/role-mappings/realm.
export async function GET(req: Request, { params }: { params: { id: string } }) {
  return handle(() => userRealmRoles(actorOf(req), params.id));
}

// Governed: the grant is parked as a change request (HTTP 202), not applied.
// 204 when the user already holds every requested role.
export async function POST(req: Request, { params }: { params: { id: string } }) {
  const roles = await req.json().catch(() => []);
  return handle(async () => (await requestGrant(actorOf(req), params.id, Array.isArray(roles) ? roles : [])) ?? undefined, 202);
}
