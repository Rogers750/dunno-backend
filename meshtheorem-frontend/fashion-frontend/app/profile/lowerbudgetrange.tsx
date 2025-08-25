import { Stack, useRouter } from "expo-router";
import { useState } from "react";
import {
    FlatList,
    SafeAreaView,
    StyleSheet,
    Text,
    TouchableOpacity,
    View,
} from "react-native";
import { API_URL } from "../../constants/api";
import { tokenStore } from "../../lib/token";

const LOWER_BUDGETS = ["500-1000", "1000-1600", "1600-2500", "Budget Not A Bar"];

export default function LowerBudgetRangeScreen() {
  const [selected, setSelected] = useState<string | null>(null);
  const router = useRouter();

  const saveBudget = async () => {
    if (!selected) return;
    try {
      const token = await tokenStore.get();
      const res = await fetch(`${API_URL}/user/profile`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ lower_budget_range: selected }),
      });
      if (res.ok) {
        router.replace("/profile/tshirtbudgetrange");
      }
    } catch (error) {
      console.error("Error saving lower budget:", error);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      {/* ✅ Hide default expo-router header */}
      <Stack.Screen options={{ headerShown: false }} />

      <View style={styles.container}>
        <Text style={styles.title}>Budget Range</Text>
        <Text style={styles.subtitle}>When you are buying</Text>
        <Text style={styles.category}>Jeans / Pants / Lowers / Cargos</Text>

        <FlatList
          data={LOWER_BUDGETS}
          numColumns={2}
          keyExtractor={(item) => item}
          columnWrapperStyle={{ justifyContent: "space-between" }}
          contentContainerStyle={styles.grid}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={[
                styles.option,
                selected === item && styles.optionSelected,
              ]}
              onPress={() => setSelected(item)}
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
          )}
          ListFooterComponent={
            <View style={styles.footer}>
              {selected ? (
                <TouchableOpacity
                  style={styles.continueButton}
                  onPress={saveBudget}
                >
                  <Text style={styles.continueText}>Continue →</Text>
                </TouchableOpacity>
              ) : (
                <View style={styles.continueButtonDisabled}>
                  <Text style={styles.continueTextDisabled}>Continue →</Text>
                </View>
              )}
            </View>
          }
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#fff" },
  container: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 40,
    maxWidth: 420,
    alignSelf: "center",
    width: "100%",
  },
  title: { fontSize: 22, fontWeight: "700", textAlign: "center", marginBottom: 6 },
  subtitle: { fontSize: 14, textAlign: "center", color: "#555" },
  category: {
    fontSize: 15,
    textAlign: "center",
    fontWeight: "600",
    marginBottom: 32,
    color: "#034BFF",
  },
  grid: { paddingBottom: 24 },
  option: {
    flex: 1,
    borderWidth: 1,
    borderColor: "#ddd",
    borderRadius: 14,
    paddingVertical: 16,
    marginBottom: 16,
    marginHorizontal: 6,
    alignItems: "center",
    backgroundColor: "#fff",
  },
  optionSelected: { borderColor: "#034BFF", backgroundColor: "#E6EEFF" },
  optionText: { fontSize: 14, fontWeight: "500", color: "#333" },
  optionTextSelected: { color: "#034BFF", fontWeight: "600" },
  footer: { marginTop: 24, alignItems: "center" },
  continueButton: {
    backgroundColor: "#034BFF",
    paddingVertical: 14,
    borderRadius: 25,
    width: "100%",
    maxWidth: 320,
    alignItems: "center",
  },
  continueText: { color: "#fff", fontSize: 15, fontWeight: "600" },
  continueButtonDisabled: {
    backgroundColor: "#E0E0E0",
    paddingVertical: 14,
    borderRadius: 25,
    width: "100%",
    maxWidth: 320,
    alignItems: "center",
  },
  continueTextDisabled: { color: "#999", fontSize: 15, fontWeight: "600" },
});
