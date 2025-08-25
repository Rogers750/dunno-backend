import { Stack, useRouter } from "expo-router";
import { useState } from "react";
import {
    FlatList,
    SafeAreaView,
    StyleSheet,
    Text,
    TouchableOpacity,
    View,
} from "react-native";
import { API_URL } from "../../constants/api";
import { tokenStore } from "../../lib/token";

const SHOP_PREFERENCES = [
  "I shop for office a lot",
  "I shop for dates a lot",
  "I shop for going out with friends a lot",
  "I shop just for my casual wears a lot",
  "I shop for functions a lot",
];

export default function ShopPreferenceScreen() {
  const [selected, setSelected] = useState<string[]>([]);
  const router = useRouter();

  const togglePreference = (item: string) => {
    setSelected((prev) =>
      prev.includes(item) ? prev.filter((p) => p !== item) : [...prev, item]
    );
  };

  const savePreferences = async () => {
    if (selected.length === 0) return;
    try {
      const token = await tokenStore.get();
      const res = await fetch(`${API_URL}/user/profile`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ shop_preferences: selected }),
      });
      if (res.ok) {
        router.replace("/home/home"); // ✅ Profile complete
      }
    } catch (error) {
      console.error("Error saving preferences:", error);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      {/* ✅ Hides the default expo-router header */}
      <Stack.Screen options={{ headerShown: false }} />

      <View style={styles.container}>
        {/* Header */}
        <Text style={styles.title}>Tell us more about you</Text>
        <Text style={styles.subtitle}>
          What do you shop for the most?{"\n"}
          <Text style={styles.highlight}>(Select multiple)</Text>
        </Text>

        {/* Options */}
        <FlatList
          data={SHOP_PREFERENCES}
          keyExtractor={(item) => item}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => {
            const isSelected = selected.includes(item);
            return (
              <TouchableOpacity
                style={[styles.option, isSelected && styles.optionSelected]}
                onPress={() => togglePreference(item)}
              >
                <Text
                  style={[
                    styles.optionText,
                    isSelected && styles.optionTextSelected,
                  ]}
                >
                  {item}
                </Text>
              </TouchableOpacity>
            );
          }}
          ListFooterComponent={
            <View style={styles.footer}>
              {selected.length > 0 ? (
                <TouchableOpacity
                  style={styles.continueButton}
                  onPress={savePreferences}
                >
                  <Text style={styles.continueText}>
                    Complete Profile →
                  </Text>
                </TouchableOpacity>
              ) : (
                <View style={styles.continueButtonDisabled}>
                  <Text style={styles.continueTextDisabled}>
                    Complete Profile →
                  </Text>
                </View>
              )}
            </View>
          }
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#fff" },

  container: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 40,
    maxWidth: 480,
    alignSelf: "center",
    width: "100%",
  },

  title: {
    fontSize: 22,
    fontWeight: "700",
    textAlign: "center",
    marginBottom: 6,
  },
  subtitle: {
    fontSize: 14,
    textAlign: "center",
    color: "#555",
    marginBottom: 24,
  },
  highlight: {
    fontWeight: "700",
    color: "#034BFF",
  },

  list: { paddingBottom: 24 },

  option: {
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 12,
    paddingVertical: 14,
    paddingHorizontal: 16,
    marginBottom: 14,
    backgroundColor: "#fff",
  },
  optionSelected: {
    borderColor: "#034BFF",
    backgroundColor: "#E6EEFF",
  },
  optionText: {
    fontSize: 15,
    fontWeight: "500",
    color: "#333",
  },
  optionTextSelected: {
    color: "#034BFF",
    fontWeight: "600",
  },

  footer: {
    marginTop: 32,
    alignItems: "center",
  },
  continueButton: {
    backgroundColor: "#034BFF",
    paddingVertical: 16,
    borderRadius: 28,
    width: "100%",
    maxWidth: 360,
    alignItems: "center",
  },
  continueText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "600",
  },
  continueButtonDisabled: {
    backgroundColor: "#E0E0E0",
    paddingVertical: 16,
    borderRadius: 28,
    width: "100%",
    maxWidth: 360,
    alignItems: "center",
  },
  continueTextDisabled: {
    color: "#999",
    fontSize: 15,
    fontWeight: "600",
  },
});
