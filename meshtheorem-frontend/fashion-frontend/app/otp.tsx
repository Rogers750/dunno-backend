import { Stack, useLocalSearchParams, useRouter } from "expo-router";
import { useState } from "react";
import {
  SafeAreaView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import OnboardingHeader from "../components/OnboardingHeader";
import { API_URL } from "../constants/api";
import { tokenStore } from "../lib/token";

export default function OtpScreen() {
  const { phone } = useLocalSearchParams<{ phone?: string }>();
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const router = useRouter();

  const verifyOtp = async () => {
    if (!otp) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/auth/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: phone, otp }),
      });

      const data = await res.json();
      console.log("Verify OTP response:", res.status, data);

      if (res.ok && data.access_token) {
        await tokenStore.set(data.access_token); // ✅ save token
        router.replace("/profile/name"); // ✅ navigate to next step
      } else {
        setMessage(data.detail || "❌ Invalid OTP");
      }
    } catch (err) {
      console.error("Verify OTP error:", err);
      setMessage("⚠️ Error verifying OTP");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      {/* Hide default header */}
      <Stack.Screen options={{ headerShown: false }} />

      <View style={styles.container}>
        {/* ✅ Reusable Header */}
        <OnboardingHeader step={1} totalSteps={10} />

        {/* Title */}
        <Text style={styles.title}>Enter OTP</Text>
        <Text style={styles.subtitle}>We’ve sent an OTP to {phone}</Text>

        {/* OTP Input */}
        <TextInput
          style={styles.input}
          keyboardType="numeric"
          value={otp}
          onChangeText={setOtp}
          placeholder="Enter OTP"
          placeholderTextColor="#9ca3af"
          maxLength={6}
        />

        {/* Continue Button */}
        {otp.length === 6 ? (
          <TouchableOpacity
            style={[styles.continueButton, loading && { opacity: 0.7 }]}
            onPress={verifyOtp}
            disabled={loading}
          >
            <Text style={styles.continueText}>
              {loading ? "Verifying..." : "Continue →"}
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
    textAlign: "center",
    letterSpacing: 4, // spacing between OTP digits
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
    color: "#dc2626", // red for error
    textAlign: "center",
    fontFamily: "System",
  },
});
