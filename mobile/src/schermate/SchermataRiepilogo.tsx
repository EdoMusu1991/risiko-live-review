/**
 * Schermata 4: Riepilogo + invio.
 *
 * Mostra il bilancio della partita appena registrata:
 * - Durata video, dimensione file
 * - Numero eventi BLE catturati
 * - Giocatori
 *
 * Tre azioni:
 * 1. **Invia ora**: costruisce bundle ZIP, lo carica al backend,
 *    salva record in cronologia, reset → torna a Setup
 * 2. **Salva e basta**: costruisce il bundle ZIP, lo salva con stato
 *    "in_coda" in cronologia, reset → torna a Setup
 *    (utile se rete WiFi assente al club; si invia da casa)
 * 3. **Annulla tutto**: elimina tutto, reset → torna a Setup
 */

import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { configurazione } from "@/configurazione";
import { usaPartita } from "@/contesto/partita";
import {
  costruisciBundle,
  eliminaBundle,
  type BundleProdotto,
} from "@/servizi/bundleBuilder";
import {
  ottieniServizioGoDice,
} from "@/servizi/godice";
import { salvaRecordUpload } from "@/servizi/storageLocale";
import { caricaBundle, ErroreUpload } from "@/servizi/uploader";
import { colori, raggi, spazi, tipografia, coloreDaColoreGiocatore } from "@/tema";
import type { RecordUpload } from "@/tipi";

import type { ParametriRotteApp } from "../navigazione";

type Navigazione = NativeStackNavigationProp<ParametriRotteApp, "Riepilogo">;

type StatoSchermata =
  | { fase: "iniziale" }
  | { fase: "costruzione" }
  | { fase: "upload"; progresso: number }
  | { fase: "completato"; partita_id_server: string }
  | { fase: "salvato_locale" }
  | { fase: "errore"; messaggio: string };

export function SchermataRiepilogo() {
  const navigation = useNavigation<Navigazione>();
  const partita = usaPartita();
  const servizioGoDice = ottieniServizioGoDice();

  const [stato, setStato] = useState<StatoSchermata>({ fase: "iniziale" });

  const reg = partita.risultatoRegistrazione;
  if (!reg) {
    // Caso anomalo: nessuna registrazione. Torna alla setup.
    return (
      <SafeAreaView style={stili.contenitore}>
        <View style={stili.contenutoCentrato}>
          <Text style={stili.testoErrore}>
            Nessuna registrazione disponibile.
          </Text>
          <Pressable
            onPress={() => {
              partita.resetPartita();
              navigation.replace("Setup");
            }}
            style={stili.botSecondario}
          >
            <Text style={stili.testoBotSecondario}>Torna all'inizio</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  async function costruisciESalva(): Promise<{
    bundle: BundleProdotto;
    record: RecordUpload;
  }> {
    setStato({ fase: "costruzione" });

    const eventi = partita.ottieniEventi();
    const bundle = await costruisciBundle({
      partita_id_locale: partita.partita_id_locale,
      giocatori: partita.giocatori,
      luogo: partita.luogo,
      note: partita.note,
      device: {
        modello: configurazione.modello_device,
        os: configurazione.os_device,
        app_version: configurazione.app_version,
      },
      godice: {
        n_dadi_attaccante: partita.configurazioniDadi.filter(
          (c) => c.ruolo === "attaccante",
        ).length,
        n_dadi_difensore: partita.configurazioniDadi.filter(
          (c) => c.ruolo === "difensore",
        ).length,
        ble_id_attaccante: partita.configurazioniDadi
          .filter((c) => c.ruolo === "attaccante")
          .sort((a, b) => a.slot - b.slot)
          .map((c) => c.ble_id),
        ble_id_difensore: partita.configurazioniDadi
          .filter((c) => c.ruolo === "difensore")
          .sort((a, b) => a.slot - b.slot)
          .map((c) => c.ble_id),
      },
      registrazione: reg!,
      eventi,
    });

    const record: RecordUpload = {
      partita_id_locale: partita.partita_id_locale,
      bundle_path: bundle.zip_path,
      bundle_dimensione_byte: bundle.zip_dimensione_byte,
      data_registrazione: reg!.ts_inizio.toISOString(),
      durata_sec: reg!.durata_sec,
      n_eventi: eventi.length,
      n_giocatori: partita.giocatori.length,
      stato: "in_coda",
      errore: null,
      partita_id_server: null,
      ultimo_tentativo: null,
      n_tentativi: 0,
    };
    salvaRecordUpload(record);

    return { bundle, record };
  }

  async function inviaOra() {
    try {
      const { bundle, record } = await costruisciESalva();

      setStato({ fase: "upload", progresso: 0 });
      salvaRecordUpload({
        ...record,
        stato: "in_corso",
        ultimo_tentativo: new Date().toISOString(),
        n_tentativi: 1,
      });

      const risposta = await caricaBundle(bundle.zip_path, (frazione) => {
        setStato({ fase: "upload", progresso: frazione });
      });

      salvaRecordUpload({
        ...record,
        stato: "completato",
        partita_id_server: risposta.partita_id,
        ultimo_tentativo: new Date().toISOString(),
        n_tentativi: 1,
      });

      setStato({ fase: "completato", partita_id_server: risposta.partita_id });
    } catch (e) {
      const messaggio =
        e instanceof ErroreUpload
          ? `${e.status}: ${e.dettaglio}`
          : String(e);
      // Aggiorna record come fallito (se è stato salvato)
      try {
        salvaRecordUpload({
          partita_id_locale: partita.partita_id_locale,
          bundle_path: "",
          bundle_dimensione_byte: 0,
          data_registrazione: reg!.ts_inizio.toISOString(),
          durata_sec: reg!.durata_sec,
          n_eventi: partita.numeroEventi,
          n_giocatori: partita.giocatori.length,
          stato: "fallito",
          errore: messaggio,
          partita_id_server: null,
          ultimo_tentativo: new Date().toISOString(),
          n_tentativi: 1,
        });
      } catch {
        // ignora
      }
      setStato({ fase: "errore", messaggio });
    }
  }

  async function salvaSenzaInviare() {
    try {
      await costruisciESalva();
      setStato({ fase: "salvato_locale" });
    } catch (e) {
      setStato({ fase: "errore", messaggio: String(e) });
    }
  }

  function chiediAnnullamento() {
    Alert.alert(
      "Annullare la partita?",
      "Verranno eliminati video, eventi e tutti i dati di questa registrazione. Non è possibile recuperarli.",
      [
        { text: "No", style: "cancel" },
        {
          text: "Sì, annulla",
          style: "destructive",
          onPress: async () => {
            try {
              await eliminaBundle(partita.partita_id_locale);
            } catch {
              // ignore
            }
            await servizioGoDice.reset();
            partita.resetPartita();
            navigation.replace("Setup");
          },
        },
      ],
    );
  }

  function ricominciaDaCapo() {
    partita.resetPartita();
    navigation.replace("Setup");
  }

  // === Render per fase ===

  if (stato.fase === "completato") {
    return (
      <SafeAreaView style={stili.contenitore}>
        <View style={stili.contenutoCentrato}>
          <Text style={stili.icona}>✓</Text>
          <Text style={stili.titoloEsitoOk}>Partita inviata</Text>
          <Text style={stili.descrizioneEsito}>
            Il server ha ricevuto la registrazione.{"\n"}Identificativo:
          </Text>
          <Text style={stili.idServer}>{stato.partita_id_server}</Text>

          <Pressable
            onPress={ricominciaDaCapo}
            style={({ pressed }) => [
              stili.botPrimario,
              pressed && stili.premuto,
              { marginTop: spazi.xl },
            ]}
          >
            <Text style={stili.testoBotPrimario}>Nuova partita</Text>
          </Pressable>

          <Pressable
            onPress={() => navigation.navigate("Cronologia")}
            style={[stili.botSecondario, { marginTop: spazi.s }]}
          >
            <Text style={stili.testoBotSecondario}>Vedi cronologia</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  if (stato.fase === "salvato_locale") {
    return (
      <SafeAreaView style={stili.contenitore}>
        <View style={stili.contenutoCentrato}>
          <Text style={stili.icona}>📥</Text>
          <Text style={stili.titoloEsitoOk}>Salvato sul telefono</Text>
          <Text style={stili.descrizioneEsito}>
            Lo invierai dalla cronologia quando torni a casa con WiFi.
          </Text>

          <Pressable
            onPress={ricominciaDaCapo}
            style={({ pressed }) => [
              stili.botPrimario,
              pressed && stili.premuto,
              { marginTop: spazi.xl },
            ]}
          >
            <Text style={stili.testoBotPrimario}>Nuova partita</Text>
          </Pressable>

          <Pressable
            onPress={() => navigation.navigate("Cronologia")}
            style={[stili.botSecondario, { marginTop: spazi.s }]}
          >
            <Text style={stili.testoBotSecondario}>Vedi cronologia</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  if (stato.fase === "errore") {
    return (
      <SafeAreaView style={stili.contenitore}>
        <View style={stili.contenutoCentrato}>
          <Text style={[stili.icona, { color: colori.scarlatto }]}>⚠</Text>
          <Text style={stili.titoloErrore}>Errore</Text>
          <Text style={stili.descrizioneEsito}>{stato.messaggio}</Text>

          <Pressable
            onPress={inviaOra}
            style={({ pressed }) => [
              stili.botPrimario,
              pressed && stili.premuto,
              { marginTop: spazi.xl },
            ]}
          >
            <Text style={stili.testoBotPrimario}>Riprova invio</Text>
          </Pressable>
          <Pressable
            onPress={() => setStato({ fase: "iniziale" })}
            style={[stili.botSecondario, { marginTop: spazi.s }]}
          >
            <Text style={stili.testoBotSecondario}>Torna al riepilogo</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  if (stato.fase === "costruzione" || stato.fase === "upload") {
    const messaggio =
      stato.fase === "costruzione"
        ? "Costruzione del pacchetto…"
        : `Invio in corso… ${Math.round(stato.progresso * 100)}%`;
    return (
      <SafeAreaView style={stili.contenitore}>
        <View style={stili.contenutoCentrato}>
          <ActivityIndicator size="large" color={colori.inchiostro} />
          <Text style={stili.testoCaricamento}>{messaggio}</Text>
        </View>
      </SafeAreaView>
    );
  }

  // === Fase iniziale: riepilogo + 3 azioni ===

  return (
    <SafeAreaView style={stili.contenitore} edges={["top", "left", "right"]}>
      <ScrollView contentContainerStyle={stili.scrollBody}>
        <View style={stili.intestazione}>
          <Text style={stili.etichetta}>Registrazione completata</Text>
          <Text style={stili.titolo}>
            Tutto <Text style={stili.titoloAccento}>pronto</Text>
          </Text>
        </View>

        {/* Carte metriche */}
        <View style={stili.griglia}>
          <CartaMetrica
            valore={formattaDurata(reg.durata_sec)}
            label="Durata"
          />
          <CartaMetrica
            valore={formattaByte(reg.dimensione_byte)}
            label="Dimensione"
          />
          <CartaMetrica
            valore={String(partita.numeroEventi)}
            label="Eventi"
          />
          <CartaMetrica
            valore={String(partita.giocatori.length)}
            label="Giocatori"
          />
        </View>

        {/* Lista giocatori */}
        <View style={stili.sezione}>
          <Text style={stili.etichettaSezione}>Giocatori</Text>
          {partita.giocatori.map((g) => (
            <View key={g.colore} style={stili.rigaGiocatore}>
              <View
                style={[
                  stili.pallinoColore,
                  { backgroundColor: coloreDaColoreGiocatore(g.colore) },
                ]}
              />
              <Text style={stili.nomeGiocatore}>{g.nome}</Text>
              <Text style={stili.ordineSeduta}>#{g.ordine_seduta}</Text>
            </View>
          ))}
        </View>

        {/* Luogo / note */}
        {partita.luogo || partita.note ? (
          <View style={stili.sezione}>
            <Text style={stili.etichettaSezione}>Dettagli</Text>
            {partita.luogo ? (
              <Text style={stili.testoMeta}>📍 {partita.luogo}</Text>
            ) : null}
            {partita.note ? (
              <Text style={stili.testoMeta}>📝 {partita.note}</Text>
            ) : null}
          </View>
        ) : null}

        {/* Bottoni azione */}
        <Pressable
          onPress={inviaOra}
          style={({ pressed }) => [
            stili.botPrimario,
            pressed && stili.premuto,
            { marginTop: spazi.l },
          ]}
        >
          <Text style={stili.testoBotPrimario}>Invia al server</Text>
        </Pressable>

        <Pressable
          onPress={salvaSenzaInviare}
          style={({ pressed }) => [
            stili.botSecondario,
            { marginTop: spazi.s, alignSelf: "stretch" },
            pressed && stili.premuto,
          ]}
        >
          <Text style={stili.testoBotSecondario}>
            Salva e invia dopo
          </Text>
        </Pressable>

        <Pressable
          onPress={chiediAnnullamento}
          style={({ pressed }) => [
            stili.botPericolo,
            { marginTop: spazi.s },
            pressed && stili.premuto,
          ]}
        >
          <Text style={stili.testoBotPericolo}>Annulla tutto</Text>
        </Pressable>

        <View style={{ height: spazi.xxl }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function CartaMetrica({ valore, label }: { valore: string; label: string }) {
  return (
    <View style={stili.cartaMetrica}>
      <Text style={stili.cartaMetricaValore}>{valore}</Text>
      <Text style={stili.cartaMetricaLabel}>{label}</Text>
    </View>
  );
}

// === Format helpers ===

function formattaDurata(secondi: number): string {
  const min = Math.floor(secondi / 60);
  const sec = Math.floor(secondi % 60);
  return `${min}:${String(sec).padStart(2, "0")}`;
}

function formattaByte(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

const stili = StyleSheet.create({
  contenitore: { flex: 1, backgroundColor: colori.pergamena },
  scrollBody: { padding: spazi.l },
  contenutoCentrato: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spazi.l,
  },
  intestazione: { marginBottom: spazi.l },
  etichetta: {
    fontSize: 11,
    letterSpacing: 2.5,
    color: colori.scarlatto,
    textTransform: "uppercase",
    fontWeight: "600",
  },
  titolo: {
    fontFamily: tipografia.fontSerif,
    fontSize: 36,
    fontWeight: "900",
    color: colori.inchiostro,
    marginTop: spazi.s,
    letterSpacing: -1,
  },
  titoloAccento: { color: colori.scarlatto, fontStyle: "italic" },
  griglia: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spazi.s,
    marginBottom: spazi.l,
  },
  cartaMetrica: {
    flex: 1,
    minWidth: "45%",
    backgroundColor: colori.pergamenaChiara,
    borderRadius: raggi.medio,
    borderWidth: 1,
    borderColor: colori.linea,
    padding: spazi.m,
    alignItems: "flex-start",
  },
  cartaMetricaValore: {
    fontFamily: tipografia.fontSerif,
    fontSize: 28,
    fontWeight: "700",
    color: colori.inchiostro,
  },
  cartaMetricaLabel: {
    fontSize: 11,
    color: colori.inchiostroTenue,
    letterSpacing: 1.5,
    textTransform: "uppercase",
    marginTop: spazi.xs,
  },
  sezione: { marginBottom: spazi.l },
  etichettaSezione: {
    fontSize: 11,
    letterSpacing: 2.5,
    color: colori.inchiostroTenue,
    textTransform: "uppercase",
    fontWeight: "600",
    marginBottom: spazi.s,
  },
  rigaGiocatore: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spazi.s,
    borderBottomWidth: 1,
    borderBottomColor: colori.linea,
    gap: spazi.s,
  },
  pallinoColore: { width: 16, height: 16, borderRadius: 8 },
  nomeGiocatore: { flex: 1, fontSize: 15, color: colori.inchiostro },
  ordineSeduta: {
    fontFamily: tipografia.fontMono,
    fontSize: 12,
    color: colori.inchiostroFioco,
  },
  testoMeta: {
    fontSize: 14,
    color: colori.inchiostroTenue,
    marginVertical: spazi.xs,
  },
  botPrimario: {
    backgroundColor: colori.inchiostro,
    paddingVertical: spazi.m,
    borderRadius: raggi.medio,
    alignItems: "center",
  },
  testoBotPrimario: {
    color: colori.pergamena,
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 2,
    textTransform: "uppercase",
  },
  botSecondario: {
    paddingVertical: spazi.m,
    borderWidth: 1,
    borderColor: colori.linea,
    borderRadius: raggi.medio,
    alignItems: "center",
  },
  testoBotSecondario: {
    fontSize: 12,
    color: colori.inchiostro,
    fontWeight: "600",
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
  botPericolo: {
    paddingVertical: spazi.m,
    alignItems: "center",
  },
  testoBotPericolo: {
    fontSize: 12,
    color: colori.scarlatto,
    fontWeight: "600",
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
  premuto: { opacity: 0.7 },
  // Esito
  icona: {
    fontSize: 64,
    color: colori.successo,
    marginBottom: spazi.m,
  },
  titoloEsitoOk: {
    fontFamily: tipografia.fontSerif,
    fontSize: 28,
    fontWeight: "700",
    color: colori.inchiostro,
    marginBottom: spazi.s,
  },
  titoloErrore: {
    fontFamily: tipografia.fontSerif,
    fontSize: 28,
    fontWeight: "700",
    color: colori.scarlatto,
    marginBottom: spazi.s,
  },
  descrizioneEsito: {
    fontSize: 14,
    color: colori.inchiostroTenue,
    textAlign: "center",
    lineHeight: 22,
  },
  idServer: {
    fontFamily: tipografia.fontMono,
    fontSize: 12,
    color: colori.inchiostro,
    marginTop: spazi.s,
    paddingHorizontal: spazi.s,
    paddingVertical: spazi.xs,
    backgroundColor: colori.pergamenaChiara,
    borderRadius: raggi.piccolo,
  },
  testoCaricamento: {
    fontSize: 14,
    color: colori.inchiostroTenue,
    marginTop: spazi.l,
  },
  testoErrore: {
    fontSize: 14,
    color: colori.scarlatto,
    marginBottom: spazi.l,
    textAlign: "center",
  },
});
