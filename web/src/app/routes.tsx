import { lazy, Suspense } from "react";
import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes, useNavigate, useParams } from "react-router";
import { Entry } from "../features/entry/Entry";
import { FocusFlow } from "../features/focus/FocusFlow";
import { Today } from "../features/today/Today";
import { PlanView } from "../features/plan/PlanView";
import { InvitePage } from "../features/invite/InvitePage";
import { Followup } from "../features/followup/Followup";
import { Inbox } from "../features/inbox/Inbox";
import { MapPage } from "../features/map/MapPage";
import { YouPage } from "../features/you/YouPage";
import { ChatPage } from "../features/chat/ChatPage";
import { CardPage } from "../features/card/CardPage";
import { RequireStudent } from "./RequireStudent";
import { LiveRegion, ToastHost } from "../ui/Toast";
import { Shell } from "./Shell";
import { CoachBar } from "../demo/coach/CoachBar";
import { StageChild } from "../demo/StageChild";
import { Join } from "../demo/Join";
import { TourHome } from "../demo/coach/TourHome";
import { setNavigator } from "../demo/perform";
import { startTour } from "../demo/tourStore";
import type { Persona } from "../demo/types";

function NavBridge() {
  const nav = useNavigate();
  useEffect(() => setNavigator(to => nav(to)), [nav]);
  return null;
}

function TourDeepLink() {
  const { persona } = useParams();
  useEffect(() => {
    void startTour(persona as Persona);
  }, [persona]);
  return null;
}

const Present = lazy(() => import("../demo/present/Present").then(m => ({ default: m.Present })));
const StaffApp = lazy(() => import("../features/staff/StaffApp").then(m => ({ default: m.StaffApp })));

export function AppRouter() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Entry />} />
        <Route path="/i/:token" element={<InvitePage />} />
        <Route path="/tour" element={<TourHome />} />
        <Route path="/join" element={<Join />} />
        <Route path="/present" element={<Suspense fallback={null}><Present /></Suspense>} />
        <Route path="/tour/:persona" element={<TourDeepLink />} />
        <Route path="/focus" element={<RequireStudent><FocusFlow /></RequireStudent>} />
        <Route element={<Shell />}>
          <Route path="/next" element={<Today />} />
          <Route path="/plan/:id" element={<PlanView />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/campus" element={<Navigate to="/chat" replace />} />
          <Route path="/you" element={<YouPage />} />
          <Route path="/card" element={<CardPage />} />
          <Route path="/inbox" element={<Inbox />} />
          <Route path="/followup/:id" element={<Followup />} />
        </Route>
        <Route path="/staff/*" element={<Suspense fallback={null}><StaffApp /></Suspense>} />
        <Route path="*" element={<Entry />} />
      </Routes>
      <NavBridge />
      <StageChild />
      <CoachBar />
      <ToastHost />
      <LiveRegion />
    </BrowserRouter>
  );
}
