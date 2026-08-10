import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./i18n";
import "./styles/global.css";

async function bootstrap(): Promise<void> {
  // Demo build: install the fake-data fetch/EventSource shims before React
  // renders so the app's bootstrap calls resolve against sample data. The
  // import is guarded so demo code never ships in the normal build.
  if (import.meta.env.VITE_DEMO_MODE === "true") {
    const { installDemo } = await import("./demo/installDemo");
    installDemo();
  }

  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

void bootstrap();
