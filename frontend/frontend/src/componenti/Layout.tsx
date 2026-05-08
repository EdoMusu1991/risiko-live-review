/**
 * Layout principale dell'applicazione: header editoriale, container
 * massimo, footer minimale.
 */

import { Link, NavLink, Outlet } from "react-router-dom";
import type { ReactNode } from "react";

interface ProprietaLayout {
  children?: ReactNode;
}

export function Layout({ children }: ProprietaLayout) {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1">
        {children ?? <Outlet />}
      </main>
      <Footer />
    </div>
  );
}

function Header() {
  return (
    <header className="border-b border-inchiostro/15">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12 py-6 flex items-end justify-between gap-8">
        {/* Logo / titolo: due righe Fraunces, scarlatto sull'apice */}
        <Link
          to="/"
          className="block leading-none group"
          aria-label="Risiko Live Review — Home"
        >
          <div className="font-display text-[10px] uppercase tracking-widest text-scarlatto mb-1">
            Il Gufo · Roma
          </div>
          <h1 className="font-display font-black text-3xl md:text-4xl tracking-crisp text-inchiostro group-hover:text-scarlatto transition-colors">
            Risiko Live
            <span className="text-inchiostro-tenue font-normal italic ml-2">
              Review
            </span>
          </h1>
        </Link>

        <nav className="flex items-center gap-1">
          <VoceMenu to="/">Partite</VoceMenu>
          <VoceMenu to="/partite/nuova">Nuova partita</VoceMenu>
          <VoceMenu to="/club">Classifica club</VoceMenu>
        </nav>
      </div>
    </header>
  );
}

function VoceMenu({
  to,
  children,
}: {
  to: string;
  children: ReactNode;
}) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `px-3 py-1.5 text-xs font-sans uppercase tracking-widest border transition-colors ${
          isActive
            ? "border-inchiostro bg-inchiostro text-pergamena"
            : "border-transparent text-inchiostro-tenue hover:text-inchiostro hover:border-inchiostro/30"
        }`
      }
    >
      {children}
    </NavLink>
  );
}

function Footer() {
  return (
    <footer className="border-t border-inchiostro/15 mt-16">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12 py-6 flex items-center justify-between text-xs text-inchiostro-tenue">
        <span className="font-mono">v0.4 · backend FastAPI · risiko_engine</span>
        <span className="etichetta">Cartografia di partita</span>
      </div>
    </footer>
  );
}
