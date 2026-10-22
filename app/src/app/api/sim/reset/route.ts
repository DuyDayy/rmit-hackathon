import { resetStore } from "@/lib/sim/iga";
import { handle } from "@/lib/sim/route";

export const dynamic = "force-dynamic";

// Reset simulated roles and change requests to the initial realm (for re-running the demo).
export async function POST() {
  return handle(() => resetStore());
}
