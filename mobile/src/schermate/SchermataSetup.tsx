/**
 * Schermata 1: Setup partita.
 *
 * Permette di:
 * - Configurare i giocatori (nomi + colori, 2-6 giocatori)
 * - Inserire luogo e note
 * - Avviare la fase di scan/connect dei GoDice (apre `SchermataDadi`)
 * - Quando tutto è pronto, navigate a `Registrazione`
 */

import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import { useState } from "react";
import {
  Alert,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { usaPartita } from "@/contesto/partita";
import { colori, raggi, spazi, tipografia, coloreDaColoreGiocatore } from "@/tema";
import { COLORI_GIOCATORE, type ColoreGiocatore, type Giocatore } from "@/tipi";

import type { ParametriRotteApp } from "../navigazione";

type Navigazione = NativeStackNavigationProp<ParametriRotteApp, "Setup">;

export function SchermataSetup() {
  const navigation = useNavigation<Navigazione>();
  const partita = usaPartita();

  const [giocatori, setGiocatori] = useState<Giocatore[]>(
    partita.giocatori.length > 0
      ? partita.giocatori
      : [
          { nome: "", colore: "rosso", ordine_seduta: 1 },
          { nome: "", colore: "blu", ordine_seduta: 2 },
        ],
  );
  const [luogo, setLuogo] = useState(partita.luogo ?? "Il Gufo · Roma");
  const [note, setNote] = useState(partita.note ?? "");

  const coloriUsati = new Set(giocatori.map((g) => g.colore));
  const dadiPronti = partita.configurazioniDadi.length === 6;

  function aggiungiGiocatore() {
    if (giocatori.length >= 6) return;
    const liberoColore =
      COLORI_GIOCATORE.find((c) => !coloriUsati.has(c)) ?? "rosso";
    setGiocatori([
      ...giocatori,
      {
        nome: "",
        colore: liberoColore,
        ordine_seduta: giocatori.length + 1,
      },
    ]);
  }

  function rimuoviGiocatore(idx: number) {
    if (giocatori.length <= 2) return;
    setGiocatori(
      giocatori
        .filter((_, i) => i !== idx)
        .map((g, i) => ({ ...g, ordine_seduta: i + 1 })),
    );
  }

  function aggiornaGiocatore(idx: number, modifiche: Partial<Giocatore>) {
    setGiocatori(
      giocatori.map((g, i) => (i === idx ? { ...g, ...modifiche } : g)),
    );
  }

  function vaiAiDadi() {
    if (giocatori.some((g) => !g.nome.trim())) {
      Alert.alert("Manca un nome", "Tutti i giocatori devono avere un nome.");
      return;
    }
    if (coloriUsati.size !== giocatori.length) {
      Alert.alert(
        "Colori duplicati",
        "Ogni giocatore deve avere un colore distinto.",
      );
      return;
    }

    // Salva nello state
    partita.setGiocatori(giocatori);
    partita.setLuogo(luogo.trim() || null);
    partita.setNote(note.trim() || null);

    navigation.navigate("Dadi");
  }

  function vaiAllaRegistrazione() {
    partita.setGiocatori(giocatori);
    partita.setLuogo(luogo.trim() || null);
    partita.setNote(note.trim() || null);
    navigation.navigate("Registrazione");
  }

  return (
    <SafeAreaView style={stili.contenitore} edges={["top", "left", "right"]}>
      <ScrollView contentContainerStyle={stili.scrollBody}>
        {/* Titolo */}
        <View style={stili.intestazione}>
          <Text style={stili.etichetta}>Nuova partita</Text>
          <Text style={stili.titolo}>
            Imposta <Text style={stili.titoloAccento}>il tavolo</Text>
          </Text>
        </View>

        {/* Sezione metadati */}
        <View style={stili.sezione}>
          <Text style={stili.etichettaSezione}>Dettagli partita</Text>

          <View style={stili.campo}>
            <Text style={stili.labelCampo}>Luogo</Text>
            <TextInput
              style={stili.input}
              value={luogo}
              onChangeText={setLuogo}
              placeholder="Il Gufo · Roma"
              placeholderTextColor={colori.inchiostroFioco}
            />
          </View>

          <View style={stili.campo}>
            <Text style={stili.labelCampo}>Note</Text>
            <TextInput
              style={[stili.input, stili.inputMulti]}
              value={note}
              onChangeText={setNote}
              placeholder="Annotazioni libere…"
              placeholderTextColor={colori.inchiostroFioco}
              multiline
              numberOfLines={3}
            />
          </View>
        </View>

        {/* Sezione giocatori */}
        <View style={stili.sezione}>
          <View style={stili.righTitoloSezione}>
            <Text style={stili.etichettaSezione}>
              Giocatori ({giocatori.length}/6)
            </Text>
            <Pressable
              onPress={aggiungiGiocatore}
              disabled={giocatori.length >= 6}
              style={({ pressed }) => [
                stili.botSecondario,
                giocatori.length >= 6 && stili.disabilitato,
                pressed && stili.premuto,
              ]}
            >
              <Text style={stili.testoBotSecondario}>+ Aggiungi</Text>
            </Pressable>
          </View>

          {giocatori.map((g, idx) => (
            <RigaGiocatore
              key={idx}
              giocatore={g}
              indice={idx}
              coloriUsati={coloriUsati}
              onModifica={(m) => aggiornaGiocatore(idx, m)}
              onRimuovi={() => rimuoviGiocatore(idx)}
              rimovibile={giocatori.length > 2}
            />
          ))}
        </View>

        {/* Sezione dadi */}
        <View style={stili.sezione}>
          <Text style={stili.etichettaSezione}>Dadi GoDice</Text>
          <Pressable
            onPress={vaiAiDadi}
            style={({ pressed }) => [
              stili.cartaAzione,
              pressed && stili.premuto,
            ]}
          >
            <View style={stili.cartaAzioneContent}>
              <Text style={stili.cartaAzioneTitolo}>
                {dadiPronti ? "✓ Dadi configurati" : "Configura i 6 dadi"}
              </Text>
              <Text style={stili.cartaAzioneDesc}>
                {dadiPronti
                  ? "3 attaccante + 3 difensore pronti"
                  : "Tocca per scansionare e collegare i GoDice"}
              </Text>
            </View>
            <Text style={stili.cartaAzioneFreccia}>›</Text>
          </Pressable>
        </View>

        {/* Bottone azione principale */}
        <Pressable
          onPress={vaiAllaRegistrazione}
          disabled={!dadiPronti}
          style={({ pressed }) => [
            stili.botPrimario,
            !dadiPronti && stili.disabilitato,
            pressed && stili.premuto,
          ]}
        >
          <Text style={stili.testoBotPrimario}>
            {dadiPronti ? "Inizia registrazione" : "Configura i dadi prima"}
          </Text>
        </Pressable>

        <View style={{ height: spazi.xxl }} />
      </ScrollView>
    </SafeAreaView>
  );
}

function RigaGiocatore({
  giocatore,
  indice,
  coloriUsati,
  onModifica,
  onRimuovi,
  rimovibile,
}: {
  giocatore: Giocatore;
  indice: number;
  coloriUsati: Set<ColoreGiocatore>;
  onModifica: (m: Partial<Giocatore>) => void;
  onRimuovi: () => void;
  rimovibile: boolean;
}) {
  return (
    <View style={stili.rigaGiocatore}>
      <Text style={stili.numGiocatore}>{indice + 1}</Text>
      <TextInput
        style={stili.inputNomeGiocatore}
        value={giocatore.nome}
        onChangeText={(nome) => onModifica({ nome })}
        placeholder="Nome"
        placeholderTextColor={colori.inchiostroFioco}
      />
      <View style={stili.coloriContainer}>
        {COLORI_GIOCATORE.map((c) => {
          const usato = c !== giocatore.colore && coloriUsati.has(c);
          const attivo = c === giocatore.colore;
          return (
            <Pressable
              key={c}
              disabled={usato}
              onPress={() => onModifica({ colore: c })}
              style={[
                stili.pallinoColore,
                {
                  backgroundColor: coloreDaColoreGiocatore(c),
                  opacity: usato ? 0.25 : 1,
                  borderWidth: attivo ? 2 : 1,
                  borderColor: attivo ? colori.inchiostro : colori.linea,
                },
              ]}
            />
          );
        })}
      </View>
      {rimovibile ? (
        <Pressable onPress={onRimuovi} style={stili.bottoneRimuovi}>
          <Text style={stili.testoRimuovi}>×</Text>
        </Pressable>
      ) : (
        <View style={stili.bottoneRimuovi} />
      )}
    </View>
  );
}

const stili = StyleSheet.create({
  contenitore: {
    flex: 1,
    backgroundColor: colori.pergamena,
  },
  scrollBody: {
    padding: spazi.l,
  },
  intestazione: {
    marginBottom: spazi.l,
  },
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
  titoloAccento: {
    color: colori.scarlatto,
    fontStyle: "italic",
  },
  sezione: {
    marginBottom: spazi.l,
  },
  righTitoloSezione: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spazi.m,
  },
  etichettaSezione: {
    fontSize: 11,
    letterSpacing: 2.5,
    color: colori.inchiostroTenue,
    textTransform: "uppercase",
    fontWeight: "600",
    marginBottom: spazi.s,
  },
  campo: {
    marginBottom: spazi.m,
  },
  labelCampo: {
    fontSize: 12,
    color: colori.inchiostroTenue,
    marginBottom: spazi.xs,
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  input: {
    backgroundColor: colori.pergamenaChiara,
    borderWidth: 1,
    borderColor: colori.linea,
    borderRadius: raggi.piccolo,
    paddingHorizontal: spazi.m,
    paddingVertical: spazi.s + 2,
    fontSize: 16,
    color: colori.inchiostro,
    fontFamily: tipografia.fontSans,
  },
  inputMulti: {
    minHeight: 80,
    textAlignVertical: "top",
  },
  rigaGiocatore: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colori.pergamenaChiara,
    borderRadius: raggi.piccolo,
    borderWidth: 1,
    borderColor: colori.linea,
    paddingHorizontal: spazi.s,
    paddingVertical: spazi.s,
    marginBottom: spazi.s,
    gap: spazi.s,
  },
  numGiocatore: {
    fontFamily: tipografia.fontMono,
    fontSize: 12,
    color: colori.inchiostroFioco,
    width: 16,
    textAlign: "center",
  },
  inputNomeGiocatore: {
    flex: 1,
    fontSize: 15,
    color: colori.inchiostro,
    fontFamily: tipografia.fontSans,
    paddingVertical: spazi.xs,
  },
  coloriContainer: {
    flexDirection: "row",
    gap: 4,
  },
  pallinoColore: {
    width: 22,
    height: 22,
    borderRadius: 11,
  },
  bottoneRimuovi: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  testoRimuovi: {
    fontSize: 24,
    color: colori.inchiostroFioco,
    fontWeight: "300",
    lineHeight: 24,
  },
  cartaAzione: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colori.pergamenaChiara,
    borderRadius: raggi.medio,
    borderWidth: 1,
    borderColor: colori.linea,
    padding: spazi.m,
  },
  cartaAzioneContent: {
    flex: 1,
  },
  cartaAzioneTitolo: {
    fontFamily: tipografia.fontSerif,
    fontSize: 18,
    fontWeight: "600",
    color: colori.inchiostro,
  },
  cartaAzioneDesc: {
    fontSize: 13,
    color: colori.inchiostroTenue,
    marginTop: 2,
  },
  cartaAzioneFreccia: {
    fontSize: 28,
    color: colori.inchiostroFioco,
    fontWeight: "300",
  },
  botPrimario: {
    backgroundColor: colori.inchiostro,
    paddingVertical: spazi.m,
    borderRadius: raggi.medio,
    alignItems: "center",
    marginTop: spazi.l,
  },
  testoBotPrimario: {
    color: colori.pergamena,
    fontSize: 14,
    fontWeight: "700",
    letterSpacing: 2,
    textTransform: "uppercase",
  },
  botSecondario: {
    paddingHorizontal: spazi.m,
    paddingVertical: spazi.s,
    borderWidth: 1,
    borderColor: colori.linea,
    borderRadius: raggi.piccolo,
  },
  testoBotSecondario: {
    fontSize: 12,
    color: colori.inchiostro,
    fontWeight: "600",
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
  disabilitato: {
    opacity: 0.4,
  },
  premuto: {
    opacity: 0.7,
  },
});
