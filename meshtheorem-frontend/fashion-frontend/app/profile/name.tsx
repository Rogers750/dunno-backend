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

export default function NameScreen() {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const router = useRouter();

  const saveName = async () => {
    if (!name) return;
    setLoading(true);

    try {
      const token = await tokenStore.get();
      if (!token) {
        setMessage("⚠️ Not logged in");
        return;
      }

      const res = await fetch(`${API_URL}/user/profile`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ username: name }),
      });

      const data = await res.json();
      if (res.ok) {
        router.replace("/profile/physical"); // 👉 next step
      } else {
        setMessage(data.detail || "❌ Failed to save name");
      }
    } catch (err) {
      console.error("Save name error:", err);
      setMessage("⚠️ Error saving name");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      {/* Hide default header */}
      <Stack.Screen options={{ headerShown: false }} />

      <View style={styles.container}>
        {/* ✅ Reusable Logo + Dots */}
        <OnboardingHeader step={2} totalSteps={10} />

        {/* Title + Subtitle */}
        <Text style={styles.title}>What’s your name?</Text>
        <Text style={styles.subtitle}>
          We’ll use this to personalize your experience
        </Text>

        {/* Input */}
        <TextInput
          style={styles.input}
          value={name}
          onChangeText={setName}
          placeholder="Enter your name"
          placeholderTextColor="#9ca3af"
        />

        {/* Continue Button */}
        {name.trim() ? (
          <TouchableOpacity
            style={[styles.continueButton, loading && { opacity: 0.7 }]}
            onPress={saveName}
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

        {/* Message */}
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

  input: {
    backgroundColor: "#f3f4f6",
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 16,
    fontSize: 16,
    color: "#000",
    width: "100%",
    marginBottom: 30,
    fontFamily: "System",
    outlineWidth: 0, // ✅ removes blue outline on web
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
