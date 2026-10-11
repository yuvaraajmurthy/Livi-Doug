import { BrowserRouter, Route, Routes } from "react-router";
import { Entry } from "../features/entry/Entry";
import { FocusFlow } from "../features/focus/FocusFlow";
import { Today } from "../features/today/Today";
import { RequireStudent } from "./RequireStudent";
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
        <Route path="/focus" element={<RequireStudent><FocusFlow /></RequireStudent>} />
        <Route element={<Shell />}>
          <Route path="/next" element={<Today />} />
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
