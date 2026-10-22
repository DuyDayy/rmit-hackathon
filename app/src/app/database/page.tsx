import path from "path";
import { DB_PATH, readRaw } from "@/lib/db";

// C3: print the database file byte-for-byte, so anyone can see the genome field is ciphertext.
export const dynamic = "force-dynamic";

export default async function DatabaseView() {
  const raw = await readRaw();
  return (
    <>
      <h1>Database view</h1>
      <p>
        Raw contents of <code>{path.relative(process.cwd(), DB_PATH)}</code> on the server. No decryption happens here.
      </p>
      {raw === null ? <p className="pending">Empty: nothing has been sealed yet.</p> : <pre className="raw">{raw}</pre>}
    </>
  );
}
