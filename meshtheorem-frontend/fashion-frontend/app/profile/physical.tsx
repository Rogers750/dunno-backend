import { Stack, useRouter } from "expo-router";
import { useState } from "react";
import {
  SafeAreaView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import OnboardingHeader from "../../components/OnboardingHeader";
import { API_URL } from "../../constants/api";
import { tokenStore } from "../../lib/token";

function feetInchesToCm(feet: number, inches: number) {
  return feet * 30.48 + inches * 2.54;
}

export default function PhysicalScreen() {
  const [feet, setFeet] = useState("");
  const [inches, setInches] = useState("");
  const [weight, setWeight] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const router = useRouter();

  const savePhysicalDetails = async () => {
    if (!feet || !weight) return;
    setLoading(true);

    try {
      const token = await tokenStore.get();
      if (!token) {
        setMessage("⚠️ Not logged in");
        return;
      }

      const heightCm = feetInchesToCm(
        parseInt(feet || "0"),
        parseInt(inches || "0")
      );

      const res = await fetch(`${API_URL}/user/profile`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          height: Math.round(heightCm),
          weight: parseFloat(weight),
        }),
      });

      const data = await res.json();
      if (res.ok) {
        router.replace("/profile/birthday"); // 👉 next step
      } else {
        setMessage(data.detail || "❌ Failed to save");
      }
    } catch (err) {
      console.error("Save physical error:", err);
      setMessage("⚠️ Error saving details");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <Stack.Screen options={{ headerShown: false }} />

      <View style={styles.container}>
        {/* ✅ Reusable Header */}
        <OnboardingHeader step={3} totalSteps={10} />

        <Text style={styles.title}>Physical Details</Text>
        <Text style={styles.subtitle}>Help us recommend the perfect fit</Text>

        {/* Invisible card wrapper */}
        <View style={styles.cardRow}>
          {/* Height row */}
          <View style={styles.row}>
            <TextInput
              style={[styles.input, styles.inputHalf]}
              keyboardType="numeric"
              value={feet}
              onChangeText={setFeet}
              placeholder="Feet"
              placeholderTextColor="#9ca3af"
            />
            <TextInput
              style={[styles.input, styles.inputHalf]}
              keyboardType="numeric"
              value={inches}
              onChangeText={setInches}
              placeholder="Inches"
              placeholderTextColor="#9ca3af"
            />
          </View>

          {/* Weight input full width */}
          <TextInput
            style={[styles.input, styles.inputFull]}
            keyboardType="numeric"
            value={weight}
            onChangeText={setWeight}
            placeholder="Weight (kg)"
            placeholderTextColor="#9ca3af"
          />
        </View>

        {/* Continue button */}
        {feet && weight ? (
          <TouchableOpacity
            style={[styles.continueButton, loading && { opacity: 0.7 }]}
            onPress={savePhysicalDetails}
            disabled={loading}
          >
            <Text style={styles.continueText}>
              {loading ? "Saving..." : "Continue →"}
            </Text>
          </TouchableOpacity>
        ) : (
          <View style={styles.continueButtonDisabled}>
            <Text style={styles.continueTextDisabled}>Continue →</Text>
          </View>
        )}

        {message ? <Text style={styles.message}>{message}</Text> : null}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#fff" },

  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "flex-start",
    paddingHorizontal: 20,
    paddingTop: 40,
    maxWidth: 400,
    alignSelf: "center",
    width: "100%",
  },

  title: {
    fontSize: 24,
    fontWeight: "700",
    textAlign: "center",
    marginBottom: 8,
    color: "#111",
    fontFamily: "System",
  },
  subtitle: {
    fontSize: 14,
    textAlign: "center",
    color: "#555",
    marginBottom: 30,
    fontFamily: "System",
  },

  cardRow: {
    width: "100%",
    marginBottom: 20,
  },

  row: {
    flexDirection: "row",
    width: "100%",
    gap: 10, // ✅ equal gap between feet & inches
    marginBottom: 12,
  },

  input: {
    backgroundColor: "#f3f4f6",
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 16,
    fontSize: 16,
    color: "#000",
    fontFamily: "System",
    outlineWidth: 0, // ✅ removes ugly blue outline on web
  },

  inputHalf: {
    flex: 1, // ✅ ensures equal halves
  },

  inputFull: {
    width: "100%", // ✅ aligns exactly with above row
  },

  continueButton: {
    backgroundColor: "#2563eb",
    paddingVertical: 16,
    borderRadius: 30,
    alignItems: "center",
    width: "100%",
  },
  continueText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
    fontFamily: "System",
  },
  continueButtonDisabled: {
    backgroundColor: "#e5e7eb",
    paddingVertical: 16,
    borderRadius: 30,
    alignItems: "center",
    width: "100%",
  },
  continueTextDisabled: {
    color: "#9ca3af",
    fontSize: 16,
    fontWeight: "600",
    fontFamily: "System",
  },

  message: {
    marginTop: 15,
    fontSize: 14,
    color: "#dc2626",
    textAlign: "center",
    fontFamily: "System",
  },
});
