// Minimal file store for C1. Holds ciphertext only; it has no way to decrypt.
import { promises as fs } from "fs";
import path from "path";

export type ParticipantRecord = {
  participantId: string;
  displayName: string;
  consent: { cancerResearch: boolean; commercialAiTraining: boolean };
  genome: string;
  updatedAt: string;
};

export const DB_PATH = path.resolve(process.cwd(), process.env.GENOME_DB_PATH ?? "data/genomes.json");

// Raw file contents exactly as on disk, for the Database view.
export async function readRaw(): Promise<string | null> {
  try {
    return await fs.readFile(DB_PATH, "utf8");
  } catch {
    return null;
  }
}

export async function readAll(): Promise<ParticipantRecord[]> {
  try {
    return JSON.parse(await fs.readFile(DB_PATH, "utf8"));
  } catch {
    return [];
  }
}

export async function upsert(record: ParticipantRecord): Promise<void> {
  const all = (await readAll()).filter((r) => r.participantId !== record.participantId);
  all.push(record);
  await fs.mkdir(path.dirname(DB_PATH), { recursive: true });
  await fs.writeFile(DB_PATH, JSON.stringify(all, null, 2));
}
