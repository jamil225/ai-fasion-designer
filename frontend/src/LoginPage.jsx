import { useEffect, useRef } from "react";
import { useAuth } from "./AuthContext";
import "./LoginPage.css";

export default function LoginPage() {
  const { initializeGoogleButton, googleClientId } = useAuth();
  const googleBtnRef = useRef(null);

  useEffect(() => {
    if (!googleClientId) return;

    // Wait for Google Identity Services script to load
    const interval = setInterval(() => {
      if (window.google?.accounts?.id && googleBtnRef.current) {
        initializeGoogleButton(googleBtnRef.current);
        clearInterval(interval);
      }
    }, 100);

    return () => clearInterval(interval);
  }, [initializeGoogleButton, googleClientId]);

  return (
    <div className="login-page">
      {/* Left panel — fashion editorial image (real grid column) */}
      <div className="login-image-panel">
        <div className="login-image-brand">
          <div className="login-image-brand-name">AI Fashion</div>
          <div className="login-image-brand-tagline">Curated by Intelligence</div>
        </div>
      </div>

      {/* Right panel — sign-in card */}
      <div className="login-card-panel">
        <div className="login-card">
          <div className="login-logo">
            <span className="login-logo-icon">✦</span>
          </div>
          <h1 className="login-title">
            AI Fashion <span className="login-title-accent">Designer</span>
          </h1>
          <p className="login-subtitle">
            Vision-first garment search powered by Gemini + Pinecone
          </p>

          <div className="login-divider" />

          {googleClientId ? (
            <>
              <p className="login-prompt">Sign in to continue</p>
              <div className="google-btn-wrapper" ref={googleBtnRef} />
            </>
          ) : (
            <div className="login-error">
              <p>⚠️ Google Client ID not configured</p>
              <p className="login-error-sub">
                Set <code>VITE_GOOGLE_CLIENT_ID</code> in{" "}
                <code>frontend/.env</code>
              </p>
            </div>
          )}

          <div className="login-footer">
            <div className="login-security-badge">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              <span>Secured with HttpOnly cookies · No tokens in browser</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
