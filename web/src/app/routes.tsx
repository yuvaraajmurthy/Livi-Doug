import { BrowserRouter, Route, Routes } from "react-router";
import { Entry } from "../features/entry/Entry";
import { FocusFlow } from "../features/focus/FocusFlow";
import { Today } from "../features/today/Today";
import { PlanView } from "../features/plan/PlanView";
import { InvitePage } from "../features/invite/InvitePage";
import { Followup } from "../features/followup/Followup";
import { Inbox } from "../features/inbox/Inbox";
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
        <Route path="/i/:token" element={<InvitePage />} />
        <Route path="/focus" element={<RequireStudent><FocusFlow /></RequireStudent>} />
        <Route element={<Shell />}>
          <Route path="/next" element={<Today />} />
          <Route path="/plan/:id" element={<PlanView />} />
          <Route path="/map" element={<Placeholder name="Map" />} />
          <Route path="/campus" element={<Placeholder name="Campus" />} />
          <Route path="/you" element={<Placeholder name="You" />} />
          <Route path="/inbox" element={<Inbox />} />
          <Route path="/followup/:id" element={<Followup />} />
        </Route>
        <Route path="*" element={<Entry />} />
      </Routes>
      <ToastHost />
      <LiveRegion />
    </BrowserRouter>
  );
}
