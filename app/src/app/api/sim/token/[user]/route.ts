import { claimsFor } from "@/lib/sim/iga";
import { handle } from "@/lib/sim/route";

export const dynamic = "force-dynamic";

// Simulated token claims for a persona (sub, preferred_username, realm_access.roles, ...).
export async function GET(_req: Request, { params }: { params: { user: string } }) {
  return handle(() => claimsFor(params.user));
}
