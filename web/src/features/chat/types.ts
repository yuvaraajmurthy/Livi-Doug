// Chat + voice UI contract (spec 2026-10-11 §3.6, §4). Shared by the chat thread and the voice overlay.
import type { CommitResponse, CrisisResponse, SupportCard } from "../../api/client";

/** One event button under a Compass message. */
export type EventChip = {
  id: string;
  title: string;
  when_label: string;
  venue: string | null;
  cost_label: string;
  synthetic: boolean;
  kind: string;
};

/** UI blocks the agent's tools emit (same payloads over chat SSE and the voice WebSocket "ui" frame). */
export type UIEvent =
  | { type: "events"; items: EventChip[] }
  | { type: "plan"; plan: CommitResponse }
  | { type: "memory"; id: string; statement: string; kind: string }
  | { type: "memory_removed"; id: string }
  | { type: "support"; card: SupportCard }
  | { type: "crisis"; crisis: CrisisResponse };

/** Server-sent events on POST /chat. */
export type ChatSSE =
  | { event: "meta"; data: { conversation_id: string; now: string } }
  | { event: "status"; data: { text: string } }
  | { event: "delta"; data: { text: string } }
  | { event: "events"; data: { items: EventChip[] } }
  | { event: "plan"; data: CommitResponse }
  | { event: "memory"; data: { id: string; statement: string; kind: string } }
  | { event: "memory_removed"; data: { id: string } }
  | { event: "support"; data: SupportCard }
  | { event: "crisis"; data: CrisisResponse }
  | { event: "done"; data: { message_id: number; source: "ai" | "fallback" } }
  | { event: "error"; data: { message: string } };

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  blocks: UIEvent[];
  at?: string;
  pending?: boolean;
  status?: string | null;
  source?: "ai" | "fallback";
};

/** GET /items/{id} (spec §3.7). */
export type ItemDetail = {
  id: string;
  kind: string;
  title: string;
  summary: string | null;
  dimensions: string[];
  synthetic: boolean;
  starts_at: string | null;
  ends_at: string | null;
  when_label: string;
  venue: string | null;
  address: string | null;
  lat: number | null;
  lon: number | null;
  campus: string;
  cost: string;
  cost_label: string;
  url: string | null;
  phone: string | null;
  hours_text: string | null;
  walk_min: number | null;
  going: { count: number | null; label: string };
  source: { name: string; url: string | null; verified_on: string | null };
  directions_url: string;
  ics_url: string | null;
};
