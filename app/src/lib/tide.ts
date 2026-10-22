"use client";

// One hook for every page: the real TideCloak SDK, or the simulation when
// NEXT_PUBLIC_TIDE_MODE=simulated (npm run dev:sim). The mode is fixed at build time,
// so the branch below never changes between renders.
import { useTideCloak } from "@tidecloak/nextjs";
import { useSimTideCloak } from "./sim/SimTideCloakProvider";
import type { TideLike } from "./tide-types";

export const TIDE_MODE: "simulated" | "tidecloak" =
  process.env.NEXT_PUBLIC_TIDE_MODE === "simulated" ? "simulated" : "tidecloak";

export function useTide(): TideLike {
  // eslint-disable-next-line react-hooks/rules-of-hooks
  return TIDE_MODE === "simulated" ? useSimTideCloak() : (useTideCloak() as unknown as TideLike);
}
