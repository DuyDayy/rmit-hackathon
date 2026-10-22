import Link from "next/link";

export default function Home() {
  return (
    <>
      <h1>Unsellable</h1>
      <p>Owning the company does not mean owning the keys.</p>
      <ul>
        <li>
          <Link href="/genome">My genome</Link>: <code>maya</code> seals and opens her synthetic genome.
        </li>
        <li>
          <Link href="/admin">Admin</Link>: <code>admin.acquirer</code> tries to export or grant itself access.
        </li>
      </ul>
    </>
  );
}
