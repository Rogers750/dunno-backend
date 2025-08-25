import { Stack, useRouter } from "expo-router";
import { useState } from "react";
import {
    SafeAreaView,
    ScrollView,
    StyleSheet,
    Text,
    TouchableOpacity,
    View,
} from "react-native";
import OnboardingHeader from "../../components/OnboardingHeader";
import { API_URL } from "../../constants/api";
import { tokenStore } from "../../lib/token";

const FIT_OBSERVATIONS = [
  "My size always fits me just right",
  "They are mostly short in length",
  "They are mostly tight on the belly",
  "They mostly have long sleeves",
  "They are mostly tight on the chest",
  "They are mostly tight around the biceps",
];

export default function TshirtFitScreen() {
  const [selected, setSelected] = useState<string[]>([]);
  const router = useRouter();

  const toggleOption = (item: string) => {
    setSelected((prev) =>
      prev.includes(item) ? prev.filter((x) => x !== item) : [...prev, item]
    );
  };

  const saveFit = async () => {
    if (selected.length === 0) return; // must select at least one
    try {
      const token = await tokenStore.get();
      const res = await fetch(`${API_URL}/user/profile`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ tshirt_fit_observations: selected }),
      });

      if (res.ok) {
        router.replace("/profile/uploadphoto"); // 👉 final step
      }
    } catch (error) {
      console.error("Error saving fit observations:", error);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <Stack.Screen options={{ headerShown: false }} />

      <View style={styles.container}>
        {/* ✅ Progress dots */}
        <OnboardingHeader step={9} totalSteps={10} />

        <Text style={styles.title}>Fit Observations</Text>
        <Text style={styles.subtitle}>
          Personal t-shirt/shirt observations (select multiple if needed)
        </Text>

        {/* Scrollable options */}
        <ScrollView
          style={{ width: "100%" }}
          contentContainerStyle={styles.optionsContainer}
          showsVerticalScrollIndicator={false}
        >
          {FIT_OBSERVATIONS.map((item) => (
            <TouchableOpacity
              key={item}
              style={[
                styles.option,
                selected.includes(item) && styles.optionSelected,
              ]}
              onPress={() => toggleOption(item)}
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
          ))}
        </ScrollView>

        {/* ✅ Fixed Footer Button */}
        <View style={styles.footer}>
          {selected.length > 0 ? (
            <TouchableOpacity style={styles.continueButton} onPress={saveFit}>
              <Text style={styles.continueText}>Finish →</Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.continueButtonDisabled}>
              <Text style={styles.continueTextDisabled}>Finish →</Text>
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
    maxWidth: 400, // ✅ mobile feel on web
    alignSelf: "center",
    width: "100%",
  },

  // Titles
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
    marginBottom: 20,
  },

  // Options
  optionsContainer: {
    width: "100%",
    paddingBottom: 120, // leave space for fixed footer
  },
  option: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 14,
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
    textAlign: "center",
  },
  optionTextSelected: {
    color: "#034BFF",
    fontWeight: "600",
  },

  // ✅ Fixed footer
  footer: {
    position: "absolute",
    bottom: 20,
    left: 20,
    right: 20,
  },
  continueButton: {
    backgroundColor: "#034BFF",
    paddingVertical: 16,
    borderRadius: 30,
    alignItems: "center",
    width: "100%",
  },
  continueText: { color: "#fff", fontSize: 16, fontWeight: "600" },

  continueButtonDisabled: {
    backgroundColor: "#E0E0E0",
    paddingVertical: 16,
    borderRadius: 30,
    alignItems: "center",
    width: "100%",
  },
  continueTextDisabled: {
    color: "#9ca3af",
    fontSize: 16,
    fontWeight: "600",
  },
});
