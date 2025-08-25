import { Image, StyleSheet, View } from "react-native";

type Props = {
  step: number;
  totalSteps: number;
};

export default function OnboardingHeader({ step, totalSteps }: Props) {
  return (
    <View style={styles.wrapper}>
      {/* Logo only (already includes brand name in design) */}
      <Image
        source={require("../assets/logo/mesh_theorem_logo.png")}
        style={styles.logo}
      />

      {/* Progress Dots */}
      <View style={styles.progress}>
        {[...Array(totalSteps)].map((_, i) => (
          <View
            key={i}
            style={[styles.dot, i === step && styles.dotActive]}
          />
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    alignItems: "center",
    marginBottom: 20,
  },
  logo: {
    width: 200,  // adjust size as needed
    height: 200,
    resizeMode: "contain",
    marginBottom: 12,
  },
  progress: {
    flexDirection: "row",
    justifyContent: "center",
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#d1d5db",
    marginHorizontal: 5,
  },
  dotActive: {
    backgroundColor: "#2563eb",
    width: 10,
    height: 10,
    borderRadius: 5,
  },
});
