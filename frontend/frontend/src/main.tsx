import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./stili/globali.css";

const elementoRoot = document.getElementById("root");
if (!elementoRoot) {
  throw new Error("Elemento #root mancante in index.html");
}

ReactDOM.createRoot(elementoRoot).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
