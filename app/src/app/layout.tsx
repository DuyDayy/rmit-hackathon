import "./globals.css";
import Providers from "@/components/Providers";
import Header from "@/components/Header";

export const metadata = { title: "Unsellable" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <Header />
          <main>{children}</main>
        </Providers>
      </body>
    </html>
  );
}
