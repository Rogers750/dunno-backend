import { Stack, useRouter } from "expo-router";
import { useState } from "react";
import {
  Image,
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

const BODY_TYPES = [
  {
    key: "slim",
    title: "Lean",
    subtitle: "Slim & slender build",
    image: require("../../assets/bodytypes/slim.jpeg"),
  },
  {
    key: "average",
    title: "Balanced",
    subtitle: "Average athletic build",
    image: require("../../assets/bodytypes/average.jpeg"),
  },
  {
    key: "athletic",
    title: "Athletic",
    subtitle: "Muscular & well-built",
    image: require("../../assets/bodytypes/athletic.png"),
  },
  {
    key: "muscular",
    title: "Strong",
    subtitle: "Defined upper body",
    image: require("../../assets/bodytypes/muscular.jpeg"),
  },
  {
    key: "muscular_with_fat",
    title: "Solid Build",
    subtitle: "Muscular with fuller shape",
    image: require("../../assets/bodytypes/muscular_with_fat.jpeg"),
  },
  {
    key: "skinny_fat",
    title: "Compact",
    subtitle: "Slim with fuller midsection",
    image: require("../../assets/bodytypes/skinnyfat.png"),
  },
  {
    key: "heavyset",
    title: "Sturdy",
    subtitle: "Larger & broader frame",
    image: require("../../assets/bodytypes/heavyset.jpeg"),
  },
];

export default function BodyTypeScreen() {
  const [selected, setSelected] = useState<string | null>(null);
  const router = useRouter();

  const saveBodyType = async () => {
    if (!selected) return;
    try {
      const token = await tokenStore.get();
      const res = await fetch(`${API_URL}/user/profile`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ body_type_model: selected }),
      });
      if (res.ok) router.replace("/profile/jeansbrands");
    } catch (error) {
      console.error("Error saving body type:", error);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <Stack.Screen options={{ headerShown: false }} />
      <View style={styles.container}>
        {/* ✅ Header with logo + progress dots */}
        <OnboardingHeader step={3} totalSteps={10} />

        <Text style={styles.title}>Choose Your Body Type</Text>
        <Text style={styles.subtitle}>
          Which model resembles your body the most?
        </Text>

        {/* Cards */}
        <ScrollView
          contentContainerStyle={styles.cardsContainer}
          showsVerticalScrollIndicator={false}
        >
          {BODY_TYPES.map((item) => (
            <TouchableOpacity
              key={item.key}
              style={[
                styles.card,
                selected === item.key && styles.cardSelected,
              ]}
              onPress={() => setSelected(item.key)}
              activeOpacity={0.8}
            >
              <Image source={item.image} style={styles.cardImage} />
              <View style={styles.cardText}>
                <Text style={styles.cardTitle}>{item.title}</Text>
                <Text style={styles.cardSubtitle}>{item.subtitle}</Text>
              </View>
            </TouchableOpacity>
          ))}
        </ScrollView>

        {/* Continue Button */}
        {selected ? (
          <TouchableOpacity style={styles.continueButton} onPress={saveBodyType}>
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

  cardsContainer: {
    width: "100%",
    paddingBottom: 20,
  },
  card: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#f9fafb",
    borderRadius: 14,
    padding: 14,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: "#e5e7eb",
  },
  cardSelected: {
    borderColor: "#2563eb",
    backgroundColor: "#eaf1ff",
  },
  cardImage: {
    width: 60,
    height: 80,
    borderRadius: 8,
    resizeMode: "cover",
    marginRight: 15,
  },
  cardText: { flex: 1 },
  cardTitle: { fontSize: 16, fontWeight: "600", color: "#111" },
  cardSubtitle: { fontSize: 13, color: "#555", marginTop: 2 },

  continueButton: {
    backgroundColor: "#2563eb",
    paddingVertical: 16,
    borderRadius: 30,
    alignItems: "center",
    width: "100%",
    marginTop: "auto",
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
    marginTop: "auto",
  },
  continueTextDisabled: {
    color: "#9ca3af",
    fontSize: 16,
    fontWeight: "600",
    fontFamily: "System",
  },
});
