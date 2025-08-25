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

const JEANS_LENGTH = [
  "They always have right length",
  "Jeans are mostly short in length",
  "Jeans are mostly long in length",
];

export default function JeansLengthScreen() {
  const [selected, setSelected] = useState<string | null>(null);
  const router = useRouter();

  const saveLength = async () => {
    if (!selected) return;
    try {
      const token = await tokenStore.get();
      const res = await fetch(`${API_URL}/user/profile`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ jeans_length_experience: selected }),
      });

      if (res.ok) {
        router.replace("/profile/uppersize"); // 👉 next screen
      }
    } catch (error) {
      console.error("Error saving jeans length:", error);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <Stack.Screen options={{ headerShown: false }} />

      <View style={styles.container}>
        {/* ✅ Progress dots */}
        <OnboardingHeader step={7} totalSteps={10} />

        <Text style={styles.title}>How about jeans length?</Text>
        <Text style={styles.subtitle}>
          Tell us about your jeans length experience
        </Text>

        {/* Options */}
        <View style={styles.optionsContainer}>
          {JEANS_LENGTH.map((item) => (
            <TouchableOpacity
              key={item}
              style={[
                styles.option,
                selected === item && styles.optionSelected,
              ]}
              onPress={() => setSelected(item)}
              activeOpacity={0.8}
            >
              <Text
                style={[
                  styles.optionText,
                  selected === item && styles.optionTextSelected,
                ]}
              >
                {item}
              </Text>
            </TouchableOpacity>
          ))}

          {/* Continue button right after options */}
          {selected ? (
            <TouchableOpacity style={styles.continueButton} onPress={saveLength}>
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
    maxWidth: 400,          // ✅ mobile look on web
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

  optionsContainer: {
    width: "100%",
  },
  option: {
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 14,
    paddingVertical: 16,
    paddingHorizontal: 16,
    marginBottom: 14,
    backgroundColor: "#fff",
    justifyContent: "center",
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

  continueButton: {
    backgroundColor: "#034BFF",
    paddingVertical: 16,
    borderRadius: 30,
    alignItems: "center",
    marginTop: 20,
    width: "100%",
  },
  continueText: { color: "#fff", fontSize: 16, fontWeight: "600" },

  continueButtonDisabled: {
    backgroundColor: "#E0E0E0",
    paddingVertical: 16,
    borderRadius: 30,
    alignItems: "center",
    marginTop: 20,
    width: "100%",
  },
  continueTextDisabled: {
    color: "#9ca3af",
    fontSize: 16,
    fontWeight: "600",
  },
});
