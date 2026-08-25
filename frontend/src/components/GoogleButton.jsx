import React, { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { useNavigate } from "react-router-dom";

const GSI_SRC = "https://accounts.google.com/gsi/client";

function loadGsi() {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve(window.google);
    const existing = document.querySelector(`script[src="${GSI_SRC}"]`);
    if (existing) {
      existing.addEventListener("load", () => resolve(window.google));
      existing.addEventListener("error", reject);
      return;
    }
    const s = document.createElement("script");
    s.src = GSI_SRC;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve(window.google);
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

export default function GoogleButton({ label = "Continue with Google" }) {
  const { googleAuth } = useAuth();
  const navigate = useNavigate();
  const initRef = useRef(false);

  const clientId = process.env.REACT_APP_GOOGLE_CLIENT_ID;

  useEffect(() => {
    if (!clientId || initRef.current) return;
    initRef.current = true;
    loadGsi()
      .then((google) => {
        google.accounts.id.initialize({
          client_id: clientId,
          callback: async (response) => {
            try {
              const user = await googleAuth(response.credential);
              navigate(user.onboarded ? "/dashboard" : "/onboarding", { replace: true });
            } catch (e) {
              toast.error(e?.response?.data?.detail || "Google sign-in failed. Please try again.");
            }
          },
          ux_mode: "popup",
          auto_select: false,
        });
      })
      .catch(() => {});
  }, [clientId, googleAuth, navigate]);

  const handleClick = () => {
    if (!clientId) {
      toast.error("Google sign-in is not configured yet.");
      return;
    }
    if (!window.google?.accounts?.id) {
      toast.error("Google sign-in is still loading. Please try again in a moment.");
      return;
    }
    window.google.accounts.id.prompt();
  };

  return (
    <Button
      type="button"
      variant="outline"
      onClick={handleClick}
      data-testid="google-auth-btn"
      className="w-full h-11 gap-2 font-medium"
    >
      <svg width="18" height="18" viewBox="0 0 24 24">
        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1Z"/>
        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.99.66-2.26 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z"/>
        <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84Z"/>
        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1a11 11 0 0 0-9.82 6.06l3.66 2.84C6.71 7.3 9.14 5.38 12 5.38Z"/>
      </svg>
      {label}
    </Button>
  );
}
