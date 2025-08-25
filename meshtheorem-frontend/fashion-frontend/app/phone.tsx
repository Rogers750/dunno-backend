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
import OnboardingHeader from "../components/OnboardingHeader";
import { API_URL } from "../constants/api";

export default function PhoneScreen() {
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const sendOtp = async () => {
    if (!phone) return;
    setLoading(true);

    const fullNumber = `91${phone}`;

    try {
      const res = await fetch(`${API_URL}/auth/send-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone_number: fullNumber }),
      });

      const data = await res.json();
      if (res.ok && data.status === "success") {
        router.push(`/otp?phone=${fullNumber}`);
      } else {
        alert(data.detail || "Failed to send OTP");
      }
    } catch (err) {
      alert("Error sending OTP");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      {/* ✅ Hide Expo Router default header */}
      <Stack.Screen options={{ headerShown: false }} />

      <View style={styles.container}>
        <OnboardingHeader step={0} totalSteps={10} />

        <Text style={styles.title}>Enter your phone number</Text>
        <Text style={styles.subtitle}>
          We’ll use this to send you a one-time password
        </Text>

        <View style={styles.inputWrapper}>
          <Text style={styles.prefix}>+91</Text>
          <TextInput
            style={styles.input}
            keyboardType="phone-pad"
            value={phone}
            onChangeText={setPhone}
            placeholder="9876543210"
            placeholderTextColor="#9ca3af"
            maxLength={10}
          />
        </View>

        {phone.length === 10 ? (
          <TouchableOpacity
            style={[styles.continueButton, loading && { opacity: 0.7 }]}
            onPress={sendOtp}
            disabled={loading}
          >
            <Text style={styles.continueText}>
              {loading ? "Sending..." : "Continue →"}
            </Text>
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
  inputWrapper: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#f3f4f6",
    borderRadius: 14,
    paddingHorizontal: 12,
    marginBottom: 30,
    width: "100%",
  },
  prefix: {
    fontSize: 16,
    fontWeight: "600",
    color: "#2563eb",
    marginRight: 8,
  },
  input: {
  flex: 1,
  fontSize: 16,
  paddingVertical: 14,
  color: "#000",
  fontFamily: "System",
  outlineWidth: 0,   // ✅ no ugly blue outline
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
});
