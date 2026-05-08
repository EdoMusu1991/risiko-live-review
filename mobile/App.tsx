/**
 * App root component.
 *
 * Setup:
 * - SafeAreaProvider (per gestione notch/dynamic island)
 * - NavigationContainer
 * - NativeStackNavigator con le 5 schermate
 * - ProvenanzaPartita (state della partita corrente)
 *
 * Tema della status bar e header configurato qui per coerenza.
 */

import { NavigationContainer, type Theme } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { Pressable, StatusBar, StyleSheet, Text } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { ProvenanzaPartita } from "@/contesto/partita";
import type { ParametriRotteApp } from "@/navigazione";
import { SchermataCronologia } from "@/schermate/SchermataCronologia";
import { SchermataDadi } from "@/schermate/SchermataDadi";
import { SchermataRegistrazione } from "@/schermate/SchermataRegistrazione";
import { SchermataRiepilogo } from "@/schermate/SchermataRiepilogo";
import { SchermataSetup } from "@/schermate/SchermataSetup";
import { colori, tipografia } from "@/tema";

const Stack = createNativeStackNavigator<ParametriRotteApp>();

const tema: Theme = {
  dark: false,
  colors: {
    primary: colori.scarlatto,
    background: colori.pergamena,
    card: colori.pergamena,
    text: colori.inchiostro,
    border: colori.linea,
    notification: colori.scarlatto,
  },
};

export default function App() {
  return (
    <SafeAreaProvider>
      <ProvenanzaPartita>
        <StatusBar
          barStyle="dark-content"
          backgroundColor={colori.pergamena}
        />
        <NavigationContainer theme={tema}>
          <Stack.Navigator
            initialRouteName="Setup"
            screenOptions={{
              headerStyle: { backgroundColor: colori.pergamena },
              headerTitleStyle: {
                fontFamily: String(tipografia.fontSerif),
                fontSize: 18,
                color: colori.inchiostro,
              },
              headerTintColor: colori.inchiostro,
              headerShadowVisible: false,
              contentStyle: { backgroundColor: colori.pergamena },
            }}
          >
            <Stack.Screen
              name="Setup"
              component={SchermataSetup}
              options={({ navigation }) => ({
                title: "Risiko Live",
                headerRight: () => (
                  <Pressable
                    onPress={() => navigation.navigate("Cronologia")}
                    style={({ pressed }) => [
                      stili.linkHeader,
                      pressed && { opacity: 0.6 },
                    ]}
                  >
                    <Text style={stili.testoLinkHeader}>Cronologia</Text>
                  </Pressable>
                ),
              })}
            />
            <Stack.Screen
              name="Dadi"
              component={SchermataDadi}
              options={{
                title: "Configura dadi",
                presentation: "modal",
              }}
            />
            <Stack.Screen
              name="Registrazione"
              component={SchermataRegistrazione}
              options={{
                headerShown: false,
                gestureEnabled: false,
              }}
            />
            <Stack.Screen
              name="Riepilogo"
              component={SchermataRiepilogo}
              options={{
                title: "Riepilogo",
                headerBackVisible: false,
              }}
            />
            <Stack.Screen
              name="Cronologia"
              component={SchermataCronologia}
              options={{ title: "Cronologia" }}
            />
          </Stack.Navigator>
        </NavigationContainer>
      </ProvenanzaPartita>
    </SafeAreaProvider>
  );
}

const stili = StyleSheet.create({
  linkHeader: {
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  testoLinkHeader: {
    fontSize: 12,
    color: colori.scarlatto,
    fontWeight: "700",
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
});
