import * as ImagePicker from "expo-image-picker";
import { Stack, useRouter } from "expo-router";
import { useState } from "react";
import {
    Alert,
    Image,
    Platform,
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

export default function UploadPhotoScreen() {
  const [photo, setPhoto] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const router = useRouter();

  const pickImage = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("Permission Required", "We need access to your photos to continue.");
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      allowsEditing: true,
      aspect: [3, 4],
      quality: 0.8,
    });

    if (!result.canceled) {
      setPhoto(result.assets[0].uri);
    }
  };

  const savePhoto = async () => {
    if (!photo) return;
    setUploading(true);

    try {
      const token = await tokenStore.get();
      const formData = new FormData();

      if (Platform.OS === "web") {
        const blob = await fetch(photo).then((res) => res.blob());
        formData.append("file", blob, "profile.jpg");
      } else {
        formData.append("file", {
          uri: photo,
          type: "image/jpeg",
          name: "profile.jpg",
        } as any);
      }

      formData.append("is_primary", "false");

      const res = await fetch(`${API_URL}/user/upload-photo`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (res.ok) {
        router.replace("/profile/generatingprofile");
      } else {
        const msg = await res.text();
        Alert.alert("Upload Failed", msg || "Something went wrong. Try again.");
      }
    } catch (error) {
      console.error("Error uploading photo:", error);
      Alert.alert("Upload Failed", "Please check your internet and try again.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <Stack.Screen options={{ headerShown: false }} />

      {/* Scrollable content */}
      <ScrollView
        style={{ flex: 1, width: "100%" }}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.container}>
          {/* Progress Header */}
          <OnboardingHeader step={10} totalSteps={10} />

          <Text style={styles.title}>Upload Your Photo</Text>
          <Text style={styles.subtitle}>
            Upload your photo in one of these poses
          </Text>

          {/* Pose example */}
          <View style={styles.poseWrapper}>
            <Image
              source={require("../../assets/poses/poses.png")}
              style={styles.poseImage}
            />
          </View>
          <Text style={styles.poseText}>
            Choose any of these poses for best results
          </Text>

          {/* Upload Box / Preview */}
          <TouchableOpacity style={styles.uploadBox} onPress={pickImage}>
            {photo ? (
              <Image
                source={{ uri: photo }}
                style={styles.previewImage}
                resizeMode="contain"
              />
            ) : (
              <Text style={styles.uploadText}>📷 Tap to upload your photo</Text>
            )}
          </TouchableOpacity>
        </View>
      </ScrollView>

      {/* ✅ Fixed Footer */}
      <View style={styles.footer}>
        {photo ? (
          <TouchableOpacity
            style={[styles.continueButton, uploading && { opacity: 0.6 }]}
            onPress={savePhoto}
            disabled={uploading}
          >
            <Text style={styles.continueText}>
              {uploading ? "Uploading..." : "That’s it, your style journey begins! →"}
            </Text>
          </TouchableOpacity>
        ) : (
          <View style={styles.continueButtonDisabled}>
            <Text style={styles.continueTextDisabled}>
              That’s it, your style journey begins! →
            </Text>
          </View>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#fff" },

  scrollContent: {
    flexGrow: 1,
    paddingBottom: 140, // ensure content doesn't hide behind button
  },

  container: {
    flex: 1,
    alignItems: "center",
    paddingHorizontal: 20,
    paddingTop: 40,
    maxWidth: 400,
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
    marginBottom: 20,
  },

  poseWrapper: {
    width: "100%",
    backgroundColor: "#f9fafb",
    borderRadius: 16,
    padding: 10,
    marginBottom: 8,
    alignItems: "center",
  },
  poseImage: {
    width: "100%",
    height: 140,
    resizeMode: "contain",
    borderRadius: 12,
  },
  poseText: {
    textAlign: "center",
    fontSize: 13,
    color: "#777",
    marginBottom: 20,
  },

  uploadBox: {
    borderWidth: 2,
    borderStyle: "dashed",
    borderColor: "#034BFF",
    borderRadius: 12,
    padding: 40,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 20,
    width: "100%",
  },
  uploadText: {
    fontSize: 16,
    color: "#034BFF",
    fontWeight: "500",
  },
  previewImage: {
    width: "100%",
    height: 400, // bigger to allow scroll
    borderRadius: 12,
    marginTop: 10,
  },

  footer: {
    position: "absolute",
    bottom: 20,
    left: 20,
    right: 20,
  },
  continueButton: {
    backgroundColor: "#034BFF",
    paddingVertical: 16,
    borderRadius: 30,
    alignItems: "center",
    width: "100%",
  },
  continueText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
    textAlign: "center",
  },
  continueButtonDisabled: {
    backgroundColor: "#E0E0E0",
    paddingVertical: 16,
    borderRadius: 30,
    alignItems: "center",
    width: "100%",
  },
  continueTextDisabled: {
    color: "#9ca3af",
    fontSize: 16,
    fontWeight: "600",
    textAlign: "center",
  },
});
