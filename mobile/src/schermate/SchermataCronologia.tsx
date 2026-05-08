/**
 * Schermata 5: Cronologia upload.
 *
 * Lista di tutti i bundle salvati sul telefono (in coda, in corso,
 * completati, falliti). Permette di:
 * - Vedere lo stato di ogni invio
 * - Riprovare l'invio di bundle in coda o falliti
 * - Eliminare bundle obsoleti dal disco
 *
 * I record vivono in MMKV (`storageLocale.ts`).
 */

import { useFocusEffect } from "@react-navigation/native";
import { useCallback, useState } from "react";
import {
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { eliminaBundle } from "@/servizi/bundleBuilder";
import {
  aggiornaRecordUpload,
  eliminaRecordUpload,
  leggiTuttiRecordUpload,
} from "@/servizi/storageLocale";
import { caricaBundle, ErroreUpload } from "@/servizi/uploader";
import { colori, raggi, spazi, tipografia } from "@/tema";
import type { RecordUpload, StatoUpload } from "@/tipi";

export function SchermataCronologia() {
  const [records, setRecords] = useState<RecordUpload[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const ricarica = useCallback(() => {
    setRecords(leggiTuttiRecordUpload());
  }, []);

  useFocusEffect(
    useCallback(() => {
      ricarica();
    }, [ricarica]),
  );

  async function ritenta(record: RecordUpload) {
    try {
      aggiornaRecordUpload(record.partita_id_locale, {
        stato: "in_corso",
        ultimo_tentativo: new Date().toISOString(),
        n_tentativi: record.n_tentativi + 1,
        errore: null,
      });
      ricarica();

      const risposta = await caricaBundle(record.bundle_path);

      aggiornaRecordUpload(record.partita_id_locale, {
        stato: "completato",
        partita_id_server: risposta.partita_id,
      });
      ricarica();
    } catch (e) {
      const msg = e instanceof ErroreUpload ? e.dettaglio : String(e);
      aggiornaRecordUpload(record.partita_id_locale, {
        stato: "fallito",
        errore: msg,
      });
      ricarica();
      Alert.alert("Invio fallito", msg);
    }
  }

  function chiediEliminazione(record: RecordUpload) {
    Alert.alert(
      "Eliminare?",
      record.stato === "completato"
        ? "Il bundle è già stato inviato al server. Posso eliminare il file dal telefono."
        : "Verrà eliminato il file ZIP dal telefono e la partita non potrà più essere inviata.",
      [
        { text: "Annulla", style: "cancel" },
        {
          text: "Elimina",
          style: "destructive",
          onPress: async () => {
            try {
              await eliminaBundle(record.partita_id_locale);
            } catch {
              // ignora
            }
            eliminaRecordUpload(record.partita_id_locale);
            ricarica();
          },
        },
      ],
    );
  }

  return (
    <SafeAreaView
      style={stili.contenitore}
      edges={["bottom", "left", "right"]}
    >
      <ScrollView
        contentContainerStyle={stili.scrollBody}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              ricarica();
              setRefreshing(false);
            }}
          />
        }
      >
        <View style={stili.intestazione}>
          <Text style={stili.etichetta}>Cronologia</Text>
          <Text style={stili.titolo}>
            Le mie <Text style={stili.titoloAccento}>partite</Text>
          </Text>
        </View>

        {records.length === 0 ? (
          <View style={stili.vuoto}>
            <Text style={stili.testoVuoto}>
              Non hai ancora registrato nessuna partita.
            </Text>
          </View>
        ) : (
          records.map((r) => (
            <CartaPartita
              key={r.partita_id_locale}
              record={r}
              onRitenta={() => ritenta(r)}
              onElimina={() => chiediEliminazione(r)}
            />
          ))
        )}

        <View style={{ height: spazi.xxl }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function CartaPartita({
  record,
  onRitenta,
  onElimina,
}: {
  record: RecordUpload;
  onRitenta: () => void;
  onElimina: () => void;
}) {
  const dataLocale = new Date(record.data_registrazione).toLocaleString(
    "it-IT",
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    },
  );

  return (
    <View style={stili.cartaPartita}>
      <View style={stili.rigaTop}>
        <View style={{ flex: 1 }}>
          <Text style={stili.dataPartita}>{dataLocale}</Text>
          <Text style={stili.metaPartita}>
            {formattaDurata(record.durata_sec)} · {record.n_giocatori} giocatori ·{" "}
            {record.n_eventi} eventi
          </Text>
          <Text style={stili.dimensioneFile}>
            {formattaByte(record.bundle_dimensione_byte)}
          </Text>
        </View>
        <BadgeStato stato={record.stato} />
      </View>

      {record.errore ? (
        <View style={stili.boxErrore}>
          <Text style={stili.testoErrore}>{record.errore}</Text>
        </View>
      ) : null}

      {record.partita_id_server ? (
        <Text style={stili.idServer} numberOfLines={1}>
          ID server: {record.partita_id_server}
        </Text>
      ) : null}

      <View style={stili.azioniCarta}>
        {(record.stato === "in_coda" || record.stato === "fallito") && (
          <Pressable
            onPress={onRitenta}
            style={({ pressed }) => [
              stili.botAzioneCarta,
              pressed && stili.premuto,
            ]}
          >
            <Text style={stili.testoBotAzione}>
              {record.stato === "fallito" ? "Riprova" : "Invia"}
            </Text>
          </Pressable>
        )}
        <Pressable
          onPress={onElimina}
          style={({ pressed }) => [
            stili.botAzioneCarta,
            pressed && stili.premuto,
          ]}
        >
          <Text
            style={[stili.testoBotAzione, { color: colori.scarlatto }]}
          >
            Elimina
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

function BadgeStato({ stato }: { stato: StatoUpload }) {
  const config: Record<
    StatoUpload,
    { testo: string; colore: string; sfondo: string }
  > = {
    in_coda: {
      testo: "In coda",
      colore: colori.inchiostroTenue,
      sfondo: colori.pergamenaScura,
    },
    in_corso: {
      testo: "In corso",
      colore: colori.oro,
      sfondo: "rgba(168, 120, 42, 0.15)",
    },
    completato: {
      testo: "Inviata",
      colore: colori.successo,
      sfondo: "rgba(44, 74, 54, 0.15)",
    },
    fallito: {
      testo: "Fallita",
      colore: colori.errore,
      sfondo: "rgba(184, 51, 42, 0.15)",
    },
    scartato: {
      testo: "Scartata",
      colore: colori.inchiostroFioco,
      sfondo: colori.pergamenaScura,
    },
  };
  const c = config[stato];
  return (
    <View style={[stili.badge, { backgroundColor: c.sfondo }]}>
      <Text style={[stili.badgeTesto, { color: c.colore }]}>{c.testo}</Text>
    </View>
  );
}

// === Format helpers ===

function formattaDurata(secondi: number): string {
  const ore = Math.floor(secondi / 3600);
  const min = Math.floor((secondi % 3600) / 60);
  if (ore > 0) return `${ore}h ${min}m`;
  return `${min}m`;
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
  vuoto: {
    paddingVertical: spazi.xxl,
    alignItems: "center",
  },
  testoVuoto: {
    fontSize: 14,
    color: colori.inchiostroFioco,
    fontStyle: "italic",
  },
  cartaPartita: {
    backgroundColor: colori.pergamenaChiara,
    borderRadius: raggi.medio,
    borderWidth: 1,
    borderColor: colori.linea,
    padding: spazi.m,
    marginBottom: spazi.s,
  },
  rigaTop: {
    flexDirection: "row",
    alignItems: "flex-start",
  },
  dataPartita: {
    fontSize: 14,
    fontWeight: "600",
    color: colori.inchiostro,
  },
  metaPartita: {
    fontSize: 12,
    color: colori.inchiostroTenue,
    marginTop: 2,
  },
  dimensioneFile: {
    fontFamily: tipografia.fontMono,
    fontSize: 11,
    color: colori.inchiostroFioco,
    marginTop: 2,
  },
  badge: {
    paddingHorizontal: spazi.s,
    paddingVertical: spazi.xs,
    borderRadius: raggi.piccolo,
  },
  badgeTesto: {
    fontSize: 10,
    fontWeight: "700",
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
  boxErrore: {
    marginTop: spazi.s,
    padding: spazi.s,
    backgroundColor: "rgba(184, 51, 42, 0.08)",
    borderRadius: raggi.piccolo,
    borderLeftWidth: 3,
    borderLeftColor: colori.scarlatto,
  },
  testoErrore: {
    fontSize: 12,
    color: colori.scarlatto,
  },
  idServer: {
    fontFamily: tipografia.fontMono,
    fontSize: 11,
    color: colori.inchiostroFioco,
    marginTop: spazi.s,
  },
  azioniCarta: {
    flexDirection: "row",
    gap: spazi.s,
    marginTop: spazi.s,
    paddingTop: spazi.s,
    borderTopWidth: 1,
    borderTopColor: colori.linea,
  },
  botAzioneCarta: {
    paddingHorizontal: spazi.m,
    paddingVertical: spazi.xs + 2,
    borderRadius: raggi.piccolo,
  },
  testoBotAzione: {
    fontSize: 12,
    fontWeight: "700",
    letterSpacing: 1.5,
    textTransform: "uppercase",
    color: colori.inchiostro,
  },
  premuto: { opacity: 0.7 },
});
