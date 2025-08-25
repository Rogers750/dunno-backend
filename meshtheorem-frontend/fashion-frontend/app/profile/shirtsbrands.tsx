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
import OnboardingHeader from "../../components/OnboardingHeader";
import { API_URL } from "../../constants/api";
import { tokenStore } from "../../lib/token";

const SHIRT_BRANDS = [
  "Levis",
  "H&M",
  "Roadster",
  "Zara",
  "Highlander",
  "Mast & Harbour",
  "The Souled Store",
  "Powerlook",
  "Snitch",
  "Wrangler",
  "Spykar",
  "Lee",
  "Mufti",
  "Van Heusen",
];

export default function ShirtBrandsScreen() {
  const [selected, setSelected] = useState<string[]>([]);
  const router = useRouter();

  const toggleBrand = (brand: string) => {
    setSelected((prev) =>
      prev.includes(brand) ? prev.filter((b) => b !== brand) : [...prev, brand]
    );
  };

  const saveBrands = async (skip = false) => {
    try {
      const token = await tokenStore.get();
      const res = await fetch(`${API_URL}/user/profile`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          shirt_brands: skip ? [] : selected,
        }),
      });

      if (res.ok) {
        router.replace("/profile/bottomsize"); // 👉 next step
      }
    } catch (error) {
      console.error("Error saving shirt brands:", error);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <Stack.Screen options={{ headerShown: false }} />

      <View style={styles.container}>
        {/* ✅ Reusable onboarding header with dots */}
        <OnboardingHeader step={5} totalSteps={10} />

        <Text style={styles.title}>Favorite Shirt Brands</Text>
        <Text style={styles.subtitle}>
          Which brands do you wear the most for shirts/t-shirts? {"\n"}
          <Text style={styles.highlight}>(Select multiple)</Text>
        </Text>

        {/* Grid of buttons */}
        <FlatList
          data={SHIRT_BRANDS}
          numColumns={2}
          keyExtractor={(item) => item}
          contentContainerStyle={styles.grid}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={[
                styles.option,
                selected.includes(item) && styles.optionSelected,
              ]}
              onPress={() => toggleBrand(item)}
              activeOpacity={0.8}
            >
              <Text
                style={[
                  styles.optionText,
                  selected.includes(item) && styles.optionTextSelected,
                ]}
              >
                {item}
              </Text>
            </TouchableOpacity>
          )}
          showsVerticalScrollIndicator={false}
        />

        {/* Footer buttons */}
        <View style={styles.footer}>
          <TouchableOpacity
            style={styles.skipButton}
            onPress={() => saveBrands(true)}
          >
            <Text style={styles.skipText}>Skip</Text>
          </TouchableOpacity>

          {selected.length > 0 ? (
            <TouchableOpacity
              style={styles.continueButton}
              onPress={() => saveBrands()}
            >
              <Text style={styles.continueText}>Continue →</Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.continueButtonDisabled}>
              <Text style={styles.continueTextDisabled}>Continue →</Text>
            </View>
          )}
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#fff" },

  container: {
    flex: 1,
    alignItems: "center",
    paddingHorizontal: 20,
    paddingTop: 40,
    maxWidth: 400, // ✅ mobile-like width
    alignSelf: "center",
    width: "100%",
  },

  title: {
    fontSize: 22,
    fontWeight: "700",
    textAlign: "center",
    marginBottom: 6,
    color: "#111",
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

  grid: {
    paddingBottom: 100,
    width: "100%",
    justifyContent: "center",
  },

  option: {
    width: "47%", // ✅ consistent size (2 per row)
    height: 80, // ✅ taller box
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 16,
    margin: "1.5%",
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#f9fafb",
    shadowColor: "#000",
    shadowOpacity: 0.03,
    shadowOffset: { width: 0, height: 2 },
    shadowRadius: 3,
    elevation: 1,
  },
  optionSelected: {
    borderColor: "#034BFF",
    backgroundColor: "#E6EEFF",
  },
  optionText: {
    fontSize: 12,
    fontWeight: "500",
    color: "#333",
    textAlign: "center",
  },
  optionTextSelected: {
    color: "#034BFF",
    fontWeight: "600",
  },

  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: "auto",
    width: "100%",
  },
  skipButton: { padding: 12 },
  skipText: { color: "#555", fontSize: 15 },

  continueButton: {
    backgroundColor: "#034BFF",
    paddingVertical: 14,
    paddingHorizontal: 30,
    borderRadius: 30,
  },
  continueText: { color: "#fff", fontSize: 16, fontWeight: "600" },

  continueButtonDisabled: {
    backgroundColor: "#E0E0E0",
    paddingVertical: 14,
    paddingHorizontal: 30,
    borderRadius: 30,
  },
  continueTextDisabled: {
    color: "#9ca3af",
    fontSize: 16,
    fontWeight: "600",
  },
});
