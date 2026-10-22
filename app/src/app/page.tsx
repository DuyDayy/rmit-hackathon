import Link from "next/link";

const STEPS = [
  { href: "/genome", step: "Step 1 · maya", title: "Seal my genome", text: "Encrypted in the participant's browser. Only she can open it." },
  { href: "/database", step: "Step 2 · anyone", title: "Look at the database", text: "The server stores ciphertext only. No key lives here." },
  { href: "/admin", step: "Step 3 · admin.acquirer", title: "Try to take the data", text: "The new owner's admin exports, then grants itself access." },
  { href: "/quorum", step: "Step 4 · quorum seats", title: "Quorum decides", text: "2 of 3 seats must approve. Independent seats hold the majority." },
];

export default function Home() {
  return (
    <>
      <div className="hero">
        <h1>Owning the company does not mean owning the keys.</h1>
        <p className="lead">
          Unsellable is a genetic data platform where your DNA cannot be sold, transferred or exported with the company,
          because no admin, acquirer or AI ever holds the key.
        </p>
      </div>
      <div className="grid">
        {STEPS.map((s) => (
          <Link key={s.href} href={s.href} className="tile">
            <span className="step">{s.step}</span>
            <h3>{s.title}</h3>
            <p>{s.text}</p>
          </Link>
        ))}
      </div>
    </>
  );
}
