/**
 * Entry point React Native. Registra il componente root sotto il nome
 * dell'app definito in `app.json`.
 */

import { AppRegistry } from "react-native";

import App from "./App";
import { name as nomeApp } from "./app.json";

AppRegistry.registerComponent(nomeApp, () => App);
