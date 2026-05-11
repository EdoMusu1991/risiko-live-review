import { BrowserRouter, Route, Routes } from "react-router-dom";

import { Layout } from "@/componenti/Layout";
import { PaginaBundleInAttesa } from "@/pagine/PaginaBundleInAttesa";
import { PaginaClassificaClub } from "@/pagine/PaginaClassificaClub";
import PaginaDashboard from "@/pagine/PaginaDashboard";
import { PaginaDettaglioPartita } from "@/pagine/PaginaDettaglioPartita";
import { PaginaListaPartite } from "@/pagine/PaginaListaPartite";
import { PaginaNuovaPartita } from "@/pagine/PaginaNuovaPartita";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<PaginaListaPartite />} />
          <Route path="/partite/nuova" element={<PaginaNuovaPartita />} />
          <Route path="/bundle" element={<PaginaBundleInAttesa />} />
          <Route path="/dashboard" element={<PaginaDashboard />} />
          <Route
            path="/partite/:partitaId"
            element={<PaginaDettaglioPartita />}
          />
          <Route path="/club" element={<PaginaClassificaClub />} />
          <Route path="*" element={<PaginaNonTrovata />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

function PaginaNonTrovata() {
  return (
    <div className="max-w-2xl mx-auto px-6 py-24 text-center">
      <div className="etichetta-rossa mb-3">404</div>
      <h2 className="font-display text-5xl font-black mb-4">
        Pagina non trovata
      </h2>
      <p className="text-inchiostro-tenue mb-6">
        Il percorso richiesto non esiste in questa applicazione.
      </p>
      <a href="/" className="btn-primario">
        Torna alla lista partite
      </a>
    </div>
  );
}
