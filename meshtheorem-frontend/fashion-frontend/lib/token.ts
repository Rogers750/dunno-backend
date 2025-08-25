import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

const KEY = "access_token";

export const tokenStore = {
  get: async () => {
    if (Platform.OS === "web") {
      return localStorage.getItem(KEY);
    }
    return SecureStore.getItemAsync(KEY);
  },
  set: async (val: string) => {
    if (Platform.OS === "web") {
      localStorage.setItem(KEY, val);
      return;
    }
    return SecureStore.setItemAsync(KEY, val);
  },
  clear: async () => {
    if (Platform.OS === "web") {
      localStorage.removeItem(KEY);
      return;
    }
    return SecureStore.deleteItemAsync(KEY);
  },
};
