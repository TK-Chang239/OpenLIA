import type { JSX } from "react";
import { Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { DisclaimerModal } from "../components/safety/DisclaimerModal";
import { useDisclaimerGate } from "../hooks/useDisclaimerGate";

export function DisclaimerGate(): JSX.Element {
  const { status, logout } = useAuth();
  // Derive mode from auth status — "personal" when no auth server is present.
  const mode: "personal" | "company" = status === "personal" ? "personal" : "company";
  const gate = useDisclaimerGate(mode);

  const handleDecline = () => {
    if (mode === "company") {
      void logout();
    }
    // In personal mode there is no session to end; the modal stays visible
    // until the user accepts (closing the app is the only alternative).
  };

  if (gate.loading) return <></>;

  return (
    <>
      {gate.needsAcceptance && gate.disclaimer && (
        <DisclaimerModal
          text={gate.disclaimer.text}
          onAccept={() => void gate.accept()}
          onDecline={handleDecline}
        />
      )}
      <Outlet />
    </>
  );
}
