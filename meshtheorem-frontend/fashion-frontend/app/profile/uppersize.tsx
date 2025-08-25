import { Stack, useRouter } from "expo-router";
import { useState } from "react";
import {
    SafeAreaView,
    StyleSheet,
    Text,
    TouchableOpacity,
    View,
} from "react-native";
import OnboardingHeader from "../../components/OnboardingHeader";
import { API_URL } from "../../constants/api";
import { tokenStore } from "../../lib/token";

const TSHIRT_SIZES = ["S", "M", "L", "XL", "XXL"];

export default function TshirtSizeScreen() {
  const [selected, setSelected] = useState<string | null>(null);
  const router = useRouter();

  const saveSize = async () => {
    if (!selected) return;
    try {
      const token = await tokenStore.get();
      const res = await fetch(`${API_URL}/user/profile`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ tshirt_size: selected }),
      });

      if (res.ok) {
        router.replace("/profile/tshirtfit"); // 👉 next screen
      }
    } catch (error) {
      console.error("Error saving t-shirt size:", error);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <Stack.Screen options={{ headerShown: false }} />

      <View style={styles.container}>
        {/* ✅ Progress dots */}
        <OnboardingHeader step={8} totalSteps={10} />

        <Text style={styles.title}>T-shirt Size</Text>
        <Text style={styles.subtitle}>Your generally preferred size</Text>

        {/* Grid of sizes */}
        <View style={styles.grid}>
          {TSHIRT_SIZES.map((size) => (
            <TouchableOpacity
              key={size}
              style={[
                styles.option,
                selected === size && styles.optionSelected,
              ]}
              onPress={() => setSelected(size)}
              activeOpacity={0.8}
            >
              <Text
                style={[
                  styles.optionText,
                  selected === size && styles.optionTextSelected,
                ]}
              >
                {size}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Continue button right after options */}
        {selected ? (
          <TouchableOpacity style={styles.continueButton} onPress={saveSize}>
            <Text style={styles.continueText}>Continue →</Text>
          </TouchableOpacity>
        ) : (
          <View style={styles.continueButtonDisabled}>
            <Text style={styles.continueTextDisabled}>Continue →</Text>
          </View>
        )}
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
    maxWidth: 400,         // ✅ mobile feel even on web
    alignSelf: "center",
    width: "100%",
  },

  // Header
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

  // Grid
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    marginBottom: 20,
    width: "100%",
  },
  option: {
    width: "30%",             // ✅ 3 per row
    height: 70,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 14,
    margin: "1.5%",
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#fff",
  },
  optionSelected: {
    borderColor: "#034BFF",
    backgroundColor: "#E6EEFF",
  },
  optionText: {
    fontSize: 16,
    fontWeight: "500",
    color: "#333",
    textAlign: "center",
  },
  optionTextSelected: {
    color: "#034BFF",
    fontWeight: "700",
  },

  // Buttons
  continueButton: {
    backgroundColor: "#034BFF",
    paddingVertical: 16,
    borderRadius: 30,
    alignItems: "center",
    marginTop: 10,
    width: "100%",
  },
  continueText: { color: "#fff", fontSize: 16, fontWeight: "600" },

  continueButtonDisabled: {
    backgroundColor: "#E0E0E0",
    paddingVertical: 16,
    borderRadius: 30,
    alignItems: "center",
    marginTop: 10,
    width: "100%",
  },
  continueTextDisabled: {
    color: "#9ca3af",
    fontSize: 16,
    fontWeight: "600",
  },
});
