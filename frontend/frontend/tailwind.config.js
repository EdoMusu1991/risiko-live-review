/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Palette piatta (no nesting con DEFAULT) per evitare problemi con
      // @apply. Le shades pergamena sono nominate, non numerate.
      colors: {
        pergamena: "#f4ede0",
        "pergamena-chiara": "#faf6ec",
        "pergamena-scura": "#ebe1cd",
        "pergamena-aged": "#ddd0b5",
        inchiostro: "#1a1614",
        "inchiostro-tenue": "#5c5147",
        "inchiostro-fioco": "#8a7d70",
        scarlatto: "#b8332a",
        "scarlatto-scuro": "#8d2620",
        "scarlatto-chiaro": "#d24a3f",
        navale: "#1f3552",
        bottiglia: "#2c4a36",
        oro: "#a8782a",
        // Colori giocatori Risiko
        "giocatore-rosso": "#b8332a",
        "giocatore-blu": "#1f3552",
        "giocatore-verde": "#2c4a36",
        "giocatore-giallo": "#c8902b",
        "giocatore-nero": "#1a1614",
        "giocatore-viola": "#5e2d56",
      },
      fontFamily: {
        // Display: Fraunces — serif transizionale con character, weights variabili
        display: ["Fraunces", "ui-serif", "Georgia", "serif"],
        // Body: Inter Tight — sans-serif neutro
        sans: [
          "Inter Tight",
          "InterTight",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
        // Monospace per timestamps ed eventi
        mono: ["JetBrains Mono", "ui-monospace", "Menlo", "monospace"],
      },
      letterSpacing: {
        crisp: "-0.02em",
        wide: "0.02em",
        wider: "0.08em",
        widest: "0.18em",
      },
      boxShadow: {
        // Ombra discreta, "carta su scrivania"
        carta:
          "0 1px 0 rgba(26,22,20,0.04), 0 4px 16px -4px rgba(26,22,20,0.08)",
        cartaHover:
          "0 1px 0 rgba(26,22,20,0.06), 0 8px 24px -6px rgba(26,22,20,0.12)",
      },
    },
  },
  plugins: [],
};
