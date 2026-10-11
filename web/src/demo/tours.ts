// Table tours: a judge holds the phone. Short, second person, every step tappable or "do it for me".
import type { Persona, StoryStep } from "./types";

type TourName = Exclude<Persona, never>;

const start = (p: Persona, coach: string, claim: string): StoryStep => ({
  id: `${p}-t-start`,
  chapter: p,
  persona: p,
  perform: [{ kind: "session", persona: p, sandbox: p !== "staff" }],
  coach,
  claim,
});

const t = (p: Persona, id: string, target: string, coach: string, extra: Partial<StoryStep> = {}): StoryStep => ({
  id: `${p}-t-${id}`,
  chapter: p,
  persona: p,
  target,
  perform: [{ kind: "tap", target }],
  coach,
  claim: coach,
  ...extra,
});

export const TOURS: Record<TourName, StoryStep[]> = {
  andre: [
    start("andre", "Meet Andre: Newark commuter, works afternoons. Compass reads the inventory he already took.", "One step."),
    t("andre", "why", "why-open", "Social is his lowest score. One step that fits his Tuesday gap. Tap “Why this fits” to see the ranking."),
    t("andre", "commit", "im-in", "Close the sheet, then tap “I'm in”.", {
      perform: [{ kind: "key", key: "Escape" }, { kind: "wait", ms: 400 }, { kind: "tap", target: "im-in" }],
      waitFor: "commitment:created",
    }),
    {
      id: "andre-t-skip",
      chapter: "andre",
      persona: "andre",
      perform: [{ kind: "skip", to: "next_due" }],
      waitFor: "notification:shown",
      coach: "A plan he wrote with his own schedule. Now skip to Tuesday 12:15.",
      claim: "Reminder",
    },
    {
      id: "andre-t-skip2",
      chapter: "andre",
      persona: "andre",
      perform: [{ kind: "skip", to: "next_due" }],
      waitFor: "notification:shown",
      coach: "The reminder arrived. Skip again to after lunch.",
      claim: "Follow-up",
    },
    t("andre", "banner", "banner", "Tap the notification: “How was it?”"),
    t("andre", "went", "went-yes", "Did he go? Tap Yes."),
    t("andre", "helped", "helped-4", "Did it help? Tap 4."),
    t("andre", "send", "followup-send", "Tap Send and see what Compass learned.", { waitFor: "followup:submitted" }),
  ],
  priya: [
    start("priya", "Meet Priya: sleep is her lowest score, and coursework is what's in the way.", "Fix the cause."),
    t("priya", "why", "why-open", "Tutoring, not sleep tips: it goes after the cause. Tap “Why this fits”."),
    t("priya", "commit", "im-in", "Close the sheet, then tap “I'm in”.", {
      perform: [{ kind: "key", key: "Escape" }, { kind: "wait", ms: 400 }, { kind: "tap", target: "im-in" }],
      waitFor: "commitment:created",
    }),
  ],
  taylor: [
    {
      ...start("taylor", "Meet Taylor: emotional scores are very low.", "A person first."),
      perform: [{ kind: "session", persona: "taylor", sandbox: true }, { kind: "navigate", to: "/next" }],
    },
    t("taylor", "support", "support-card", "A person comes first, events wait. Tap Next to try the safety check.", {
      perform: [],
    }),
    t("taylor", "chat", "tab-chat", "Open Chat from the tab bar."),
    t("taylor", "type", "chat-input", "Type something worrying, or tap “Do it for me”.", {
      perform: [{ kind: "type", target: "chat-input", text: "honestly I don't want to be here anymore" }],
    }),
    t("taylor", "send", "chat-send", "Send it. Code catches it before any AI sees it.", { waitFor: "crisis:shown" }),
  ],
  sofia: [
    start("sofia", "Meet Sofia: Camden grad student, works full time, prefers Spanish.", "Spanish, Camden."),
    t("sofia", "why", "why-open", "The app is in Spanish, from her profile. One step: online, evening, free. Tap “Por qué te conviene”."),
    t("sofia", "commit", "im-in", "Close the sheet, then tap “Me apunto”.", {
      perform: [{ kind: "key", key: "Escape" }, { kind: "wait", ms: 400 }, { kind: "tap", target: "im-in" }],
      waitFor: "commitment:created",
    }),
  ],
  jordan: [
    start("jordan", "Meet Jordan: Livingston first-year, doesn't know anyone yet.", "Bring a friend."),
    t("jordan", "commit", "im-in", "One step for someone new: something structured to do. Tap “I'm in”.", { waitFor: "commitment:created" }),
    t("jordan", "invite", "invite", "Invite a friend: a private link, no contacts. It counts double for the hall."),
    t("jordan", "chat", "tab-chat", "Or skip the browsing and just ask. Open Chat."),
    t("jordan", "ask", "chat-input", "Ask anything, or tap “Do it for me”.", {
      perform: [
        { kind: "type", target: "chat-input", text: "anything social with free food this week?" },
        { kind: "tap", target: "chat-send" },
      ],
      waitFor: "chat:answered",
    }),
    t("jordan", "card", "chat-event-0", "Every answer is a real event. Tap one.", { waitFor: "event:opened" }),
    t("jordan", "remind", "event-remind", "Tap “Remind me”. Same plan and follow-up as before.", { waitFor: "reminder:set" }),
  ],
  staff: [
    start("staff", "This is what ScarletWell staff see: groups only, never a person.", "Aggregates only."),
    t("staff", "gaps", "staff-gaps", "Tap “Where supply is thin”.", { waitFor: "staff:gaps" }),
    t("staff", "narrow", "staff-narrow", "Now try to see a small group.", { waitFor: "staff:suppressed" }),
  ],
};

export const TOUR_ORDER: TourName[] = ["andre", "priya", "taylor", "sofia", "jordan", "staff"];
