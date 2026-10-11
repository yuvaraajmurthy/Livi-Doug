import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/geist";
import "@fontsource/instrument-serif/400.css";
import "@fontsource/instrument-serif/400-italic.css";
import "./styles/tokens.css";
import { Providers } from "./app/providers";
import { AppRouter } from "./app/routes";
import { installAutoReplay } from "./demo/replay/enable";
import { registerServiceWorker } from "./push/push";
import { startRecording } from "./api/transport";

installAutoReplay();
if (new URLSearchParams(window.location.search).get("record") === "1") startRecording();
if (import.meta.env.PROD) void registerServiceWorker();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Providers>
      <AppRouter />
    </Providers>
  </StrictMode>,
);
