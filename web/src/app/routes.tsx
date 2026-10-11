import { BrowserRouter, Route, Routes } from "react-router";
import { Entry } from "../features/entry/Entry";
import { LiveRegion, ToastHost } from "../ui/Toast";
import { Shell } from "./Shell";

function Placeholder({ name }: { name: string }) {
  return (
    <section>
      <h1 tabIndex={-1} className="text-[30px] font-semibold tracking-tight outline-none">
        {name}
      </h1>
    </section>
  );
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Entry />} />
        <Route element={<Shell />}>
          <Route path="/next" element={<Placeholder name="Today" />} />
          <Route path="/map" element={<Placeholder name="Map" />} />
          <Route path="/campus" element={<Placeholder name="Campus" />} />
          <Route path="/you" element={<Placeholder name="You" />} />
          <Route path="/inbox" element={<Placeholder name="Inbox" />} />
        </Route>
        <Route path="*" element={<Entry />} />
      </Routes>
      <ToastHost />
      <LiveRegion />
    </BrowserRouter>
  );
}
