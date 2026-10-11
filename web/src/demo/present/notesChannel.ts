import type { CallLog } from "../../api/inspector";

export const NOTES_CHANNEL = "compass-present";

export type NotesState = {
  kind: "state";
  index: number;
  status: string;
  error: string | null;
  startedAt: number | null;
  calls: CallLog[];
  templates: boolean;
  offline: boolean;
  token: string | null;
};

export type NotesCommand =
  | { kind: "next" }
  | { kind: "back" }
  | { kind: "jump"; index: number }
  | { kind: "templates" }
  | { kind: "offline" }
  | { kind: "restart" }
  | { kind: "hello" };
