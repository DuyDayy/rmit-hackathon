// Synthetic genome (C2). Lives only in the browser bundle; the server only ever receives ciphertext.
export const SYNTHETIC_GENOME = {
  markers: [
    { id: "rs0000001", genotype: "A/G" },
    { id: "rs0000002", genotype: "C/C" },
    { id: "rs0000003", genotype: "T/T" },
  ],
  note: "Synthetic data. No medical meaning.",
};

export type Genome = typeof SYNTHETIC_GENOME;

export const MAYA_ID = "p-0001";
