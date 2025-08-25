import DateTimePicker from "@react-native-community/datetimepicker";
import { Stack, useRouter } from "expo-router";
import { useState } from "react";
import {
  Platform,
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

export default function BirthdayScreen() {
  const [date, setDate] = useState<Date | null>(null);
  const [dateStr, setDateStr] = useState(""); // web fallback
  const [show, setShow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const router = useRouter();

  const onChange = (_: any, selectedDate?: Date) => {
    setShow(Platform.OS === "ios"); // keep open on iOS
    if (selectedDate) {
      setDate(selectedDate);
    }
  };

  const saveBirthday = async () => {
    try {
      let formattedDate = "";

      if (Platform.OS === "web") {
        // expect yyyy/mm/dd from user
        const [year, month, day] = dateStr.split("/").map(Number);
        if (!year || !month || !day) {
          setMessage("⚠️ Please enter a valid date (yyyy/mm/dd)");
          return;
        }
        formattedDate = `${year}/${String(month).padStart(2, "0")}/${String(
          day
        ).padStart(2, "0")}`;
      } else if (date) {
        formattedDate = date.toISOString().split("T")[0].replace(/-/g, "/");
      } else {
        setMessage("⚠️ Please select your birthday");
        return;
      }

      const token = await tokenStore.get();
      if (!token) {
        setMessage("⚠️ Not logged in");
        return;
      }

      setLoading(true);

      const res = await fetch(`${API_URL}/user/profile`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ birthday: formattedDate }),
      });

      const data = await res.json();
      if (res.ok) {
        router.replace("/profile/bodytype");
      } else {
        setMessage(data.detail || "❌ Failed to save");
      }
    } catch (err) {
      console.error("Save birthday error:", err);
      setMessage("⚠️ Error saving birthday");
    } finally {
      setLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={styles.container}>
        {/* ✅ Reusable header with logo + dots */}
        <OnboardingHeader step={4} totalSteps={10} />

        <Text style={styles.title}>When's your birthday?</Text>
        <Text style={styles.subtitle}>
          We’ll suggest age-appropriate styles
        </Text>

        {Platform.OS === "web" ? (
          <TextInput
            style={styles.input}
            placeholder="yyyy/mm/dd"
            value={dateStr}
            onChangeText={setDateStr}
            placeholderTextColor="#9ca3af"
          />
        ) : (
          <>
            <TouchableOpacity
              style={styles.chooseDateButton}
              onPress={() => setShow(true)}
            >
              <Text style={styles.chooseDateText}>📅 Choose Date</Text>
            </TouchableOpacity>

            {date && (
              <Text style={styles.dateText}>
                Selected: {date.getDate()}/{date.getMonth() + 1}/
                {date.getFullYear()}
              </Text>
            )}

            {show && (
              <DateTimePicker
                value={date || new Date(2000, 0, 1)}
                mode="date"
                display="spinner"
                onChange={onChange}
                maximumDate={new Date()} // can't pick future
              />
            )}
          </>
        )}

        {/* Continue Button */}
        {(Platform.OS === "web" ? dateStr : date) ? (
          <TouchableOpacity
            style={[styles.continueButton, loading && { opacity: 0.7 }]}
            onPress={saveBirthday}
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
    outlineWidth: 0, // ✅ remove blue outline on web
  },

  chooseDateButton: {
    backgroundColor: "#f3f4f6",
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 16,
    width: "100%",
    marginBottom: 20,
    alignItems: "center",
  },
  chooseDateText: {
    fontSize: 16,
    color: "#2563eb",
    fontWeight: "600",
  },

  dateText: {
    marginVertical: 15,
    fontSize: 16,
    textAlign: "center",
    color: "#333",
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
