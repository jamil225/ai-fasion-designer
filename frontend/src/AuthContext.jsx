import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { fetchCurrentUser, loginWithGoogle, logoutUser } from "./api";

const AuthContext = createContext(null);

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount, check if we already have a valid session cookie
  useEffect(() => {
    fetchCurrentUser()
      .then((userData) => {
        if (userData) {
          setUser(userData);
        }
      })
      .finally(() => setIsLoading(false));
  }, []);

  // Load Google Identity Services script
  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;

    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    document.head.appendChild(script);

    return () => {
      document.head.removeChild(script);
    };
  }, []);

  const handleGoogleLogin = useCallback(async (credentialResponse) => {
    try {
      const userData = await loginWithGoogle(credentialResponse.credential);
      setUser(userData);
    } catch (err) {
      console.error("Login failed:", err);
    }
  }, []);

  const handleLogout = useCallback(async () => {
    await logoutUser();
    setUser(null);
    // Revoke Google session if available
    if (window.google?.accounts?.id) {
      window.google.accounts.id.disableAutoSelect();
    }
  }, []);

  const initializeGoogleButton = useCallback((element) => {
    if (!element || !GOOGLE_CLIENT_ID || !window.google?.accounts?.id) return;

    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: handleGoogleLogin,
      auto_select: false,
    });

    window.google.accounts.id.renderButton(element, {
      theme: "filled_black",
      size: "large",
      shape: "pill",
      text: "signin_with",
      width: 300,
    });
  }, [handleGoogleLogin]);

  const value = {
    user,
    isAuthenticated: !!user,
    isLoading,
    handleLogout,
    initializeGoogleButton,
    googleClientId: GOOGLE_CLIENT_ID,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
