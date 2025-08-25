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

const BOTTOM_SIZES = ["28","30","32","34","36","38","40","42","44","46","48"];

export default function BottomSizeScreen() {
  const [selected, setSelected] = useState<string | null>(null);
  const [cols, setCols] = useState(4); // responsive columns
  const [containerW, setContainerW] = useState(0);
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
        body: JSON.stringify({ bottom_size: selected }),
      });

      if (res.ok) router.replace("/profile/jeanslenexp");
    } catch (error) {
      console.error("Error saving bottom size:", error);
    }
  };

  const onContainerLayout = (e: any) => {
    const w = e.nativeEvent.layout.width;
    setContainerW(w);
    // Simple responsive rules (tuned to your screenshot)
    if (w >= 560) setCols(4);
    else if (w >= 380) setCols(3);
    else setCols(2);
  };

  const itemWidth = cols === 4 ? "23.5%" : cols === 3 ? "31.5%" : "48%";

  return (
    <SafeAreaView style={styles.safeArea}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={styles.container} onLayout={onContainerLayout}>
        <OnboardingHeader step={6} totalSteps={10} />

        <Text style={styles.title}>Preferred Bottom Size</Text>
        <Text style={styles.subtitle}>What waist size suits you the best?</Text>

        {/* Grid */}
        <View style={styles.grid}>
          {BOTTOM_SIZES.map((sz) => (
            <TouchableOpacity
              key={sz}
              onPress={() => setSelected(sz)}
              activeOpacity={0.85}
              style={[
                styles.option,
                { width: itemWidth },
                selected === sz && styles.optionSelected,
              ]}
            >
              <Text
                style={[
                  styles.optionText,
                  selected === sz && styles.optionTextSelected,
                ]}
              >
                {sz}
              </Text>
            </TouchableOpacity>
          ))}
          {/* This spacer helps last row align nicely */}
          {cols === 4 && (BOTTOM_SIZES.length % 4 === 3) && (
            <View style={[styles.option, { width: itemWidth, opacity: 0 }]} />
          )}
        </View>

        {/* Continue */}
        <View style={styles.footer}>
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
    // Wider “mobile card” on web so 4 columns fit comfortably
    maxWidth: 640,            // ← was 400; this matches your screenshot vibe
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
    marginBottom: 22,
  },

  grid: {
    width: "100%",
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    paddingHorizontal: 8,
    marginBottom: 24,
  },

  option: {
    height: 56,
    borderWidth: 1,
    borderColor: "#e5e7eb",
    borderRadius: 16,
    marginBottom: 14,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#fff",
    // subtle depth
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
    fontSize: 16,
    fontWeight: "500",
    color: "#111",
    textAlign: "center",
  },
  optionTextSelected: {
    color: "#034BFF",
    fontWeight: "700",
  },

  footer: {
    marginTop: "auto",
    width: "100%",
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
  continueTextDisabled: { color: "#9ca3af", fontSize: 16, fontWeight: "600" },
});
