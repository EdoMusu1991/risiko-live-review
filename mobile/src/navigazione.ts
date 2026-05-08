/**
 * Configurazione del navigation stack.
 *
 * Stack lineare:
 *   Setup → Dadi (push, modale) → Setup → Registrazione (replace) → Riepilogo (replace)
 *
 * `Cronologia` è raggiungibile da Setup tramite header e da Riepilogo
 * dopo upload completato.
 */

export type ParametriRotteApp = {
  Setup: undefined;
  Dadi: undefined;
  Registrazione: undefined;
  Riepilogo: undefined;
  Cronologia: undefined;
};
