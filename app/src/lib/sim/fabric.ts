// Simulated Tide Fabric: role-gated, owner-bound field encryption, in the browser.
//
// Same rules as TideCloak's self-encryption: encrypting data tagged T needs the realm role
// _tide_T.selfencrypt, decrypting needs _tide_T.selfdecrypt, and "self" means only the user who
// sealed a value can open it. The cipher is real AES-GCM, so the server and the database only
// ever see ciphertext.
//
// NOT SECURE, simulation only: the key is derived in the browser from a constant, so anyone with
// this code could derive it. With TideCloak the key is split across the Fabric's nodes and no
// single party, browser or server holds it.

const PREFIX = "sim-tide:v1:";
const SIM_SECRET = "unsellable-simulated-fabric-not-secure";

type Sealed = { owner: string; tag: string; iv: string; ct: string };

const b64 = (bytes: Uint8Array) => btoa(String.fromCharCode(...bytes));
const unb64 = (s: string) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

async function ownerKey(owner: string, tag: string) {
  const material = await crypto.subtle.importKey("raw", new TextEncoder().encode(`${SIM_SECRET}:${owner}:${tag}`), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt: new TextEncoder().encode("sim-fabric"), iterations: 100_000, hash: "SHA-256" },
    material,
    { name: "AES-GCM", length: 256 },
    false,
    ["encrypt", "decrypt"],
  );
}

export class FabricDenied extends Error {}

export async function simEncrypt(
  items: { data: string | Uint8Array; tags: string[] }[],
  user: string,
  roles: string[],
): Promise<string[]> {
  return Promise.all(
    items.map(async ({ data, tags }) => {
      const tag = tags[0] ?? "";
      if (!roles.includes(`_tide_${tag}.selfencrypt`)) {
        throw new FabricDenied(`Simulated Fabric refused to encrypt: ${user} lacks _tide_${tag}.selfencrypt`);
      }
      const iv = crypto.getRandomValues(new Uint8Array(12));
      const plain = typeof data === "string" ? new TextEncoder().encode(data) : data;
      const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await ownerKey(user, tag), plain));
      const sealed: Sealed = { owner: user, tag, iv: b64(iv), ct: b64(ct) };
      return PREFIX + btoa(JSON.stringify(sealed));
    }),
  );
}

export async function simDecrypt(
  items: { encrypted: string | Uint8Array; tags: string[] }[],
  user: string,
  roles: string[],
): Promise<string[]> {
  return Promise.all(
    items.map(async ({ encrypted, tags }) => {
      const text = typeof encrypted === "string" ? encrypted : new TextDecoder().decode(encrypted);
      if (!text.startsWith(PREFIX)) throw new FabricDenied("Simulated Fabric: not a simulated ciphertext");
      const sealed: Sealed = JSON.parse(atob(text.slice(PREFIX.length)));
      const tag = tags[0] ?? "";
      if (sealed.tag !== tag) throw new FabricDenied(`Simulated Fabric: data is tagged ${sealed.tag}, not ${tag}`);
      if (!roles.includes(`_tide_${tag}.selfdecrypt`)) {
        throw new FabricDenied(`Simulated Fabric refused to decrypt: ${user} lacks _tide_${tag}.selfdecrypt`);
      }
      if (sealed.owner !== user) {
        throw new FabricDenied(`Simulated Fabric refused to decrypt: self-decrypt only, and this record belongs to someone else`);
      }
      const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: unb64(sealed.iv) }, await ownerKey(sealed.owner, tag), unb64(sealed.ct));
      return new TextDecoder().decode(plain);
    }),
  );
}
