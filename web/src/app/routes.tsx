import { BrowserRouter, Route, Routes } from "react-router";
import { Entry } from "../features/entry/Entry";
import { FocusFlow } from "../features/focus/FocusFlow";
import { Today } from "../features/today/Today";
import { PlanView } from "../features/plan/PlanView";
import { InvitePage } from "../features/invite/InvitePage";
import { Followup } from "../features/followup/Followup";
import { Inbox } from "../features/inbox/Inbox";
import { MapPage } from "../features/map/MapPage";
import { YouPage } from "../features/you/YouPage";
import { CampusPage } from "../features/campus/CampusPage";
import { CardPage } from "../features/card/CardPage";
import { RequireStudent } from "./RequireStudent";
import { LiveRegion, ToastHost } from "../ui/Toast";
import { Shell } from "./Shell";

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
          <Route path="/map" element={<MapPage />} />
          <Route path="/campus" element={<CampusPage />} />
          <Route path="/you" element={<YouPage />} />
          <Route path="/card" element={<CardPage />} />
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
