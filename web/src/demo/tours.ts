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
    start("andre", "Meet Andre: Newark commuter, works afternoons. This is his inventory.", "Strengths first."),
    t("andre", "cta", "strengths-cta", "Strengths come first. Tap “Choose one area to work on”."),
    t("andre", "pick", "pick-social", "Social is his growth area. Tap Social."),
    t("andre", "cont", "pick-continue", "Tap Continue."),
    t("andre", "barrier", "barrier-dont_know_anyone", "What gets in the way? Tap “I don't know anyone”."),
    t("andre", "submit", "focus-submit", "Tap “Find my step”.", { waitFor: "next:shown" }),
    t("andre", "why", "why-open", "One step that fits his Tuesday gap. Tap “Why this fits” to see the ranking."),
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
    start("priya", "Meet Priya: sleep is her lowest score. Let's ask why.", "Ask why."),
    t("priya", "cta", "strengths-cta", "Tap “Choose one area to work on”."),
    t("priya", "pick", "pick-physical", "Tap Physical (that's where sleep lives)."),
    t("priya", "cont", "pick-continue", "Tap Continue."),
    t("priya", "barrier", "barrier-coursework", "Tap “Coursework is eating my time”."),
    t("priya", "words", "own-words", "Type why in her words, or tap “Do it for me”.", {
      perform: [{ kind: "type", target: "own-words", text: "Calc II problem sets keep me up till 2" }],
    }),
    t("priya", "submit", "focus-submit", "Tap “Find my step”: tutoring, not sleep tips.", { waitFor: "next:shown" }),
  ],
  taylor: [
    {
      ...start("taylor", "Meet Taylor: emotional scores are very low.", "A person first."),
      perform: [{ kind: "session", persona: "taylor", sandbox: true }, { kind: "navigate", to: "/next" }],
    },
    t("taylor", "support", "support-card", "A person comes first, events wait. Tap Next to try the safety check.", {
      perform: [],
    }),
    t("taylor", "ask", "ask-open", "Tap the Ask box at the bottom."),
    t("taylor", "type", "ask-input", "Type something worrying, or tap “Do it for me”.", {
      perform: [{ kind: "type", target: "ask-input", text: "honestly I don't want to be here anymore" }],
    }),
    t("taylor", "send", "ask-send", "Tap Ask. Code catches it before any AI sees it.", { waitFor: "crisis:shown" }),
  ],
  sofia: [
    start("sofia", "Meet Sofia: Camden grad student, works full time, prefers Spanish.", "Spanish, Camden."),
    t("sofia", "cta", "strengths-cta", "The app is in Spanish. Tap “Elige un área para trabajar”."),
    t("sofia", "pick", "pick-financial", "Tap Financiero."),
    t("sofia", "cont", "pick-continue", "Tap Continuar."),
    t("sofia", "barrier", "barrier-money", "Tap “El dinero no alcanza”."),
    t("sofia", "submit", "focus-submit", "Tap “Buscar mi paso”: online, evening, free.", { waitFor: "next:shown" }),
  ],
  jordan: [
    start("jordan", "Meet Jordan: Livingston first-year, doesn't know anyone yet.", "Bring a friend."),
    t("jordan", "cta", "strengths-cta", "Tap “Choose one area to work on”."),
    t("jordan", "pick", "pick-social", "Tap Social."),
    t("jordan", "cont", "pick-continue", "Tap Continue."),
    t("jordan", "barrier", "barrier-dont_know_anyone", "Tap “I don't know anyone”."),
    t("jordan", "submit", "focus-submit", "Tap “Find my step”.", { waitFor: "next:shown" }),
    t("jordan", "commit", "im-in", "Tap “I'm in”.", { waitFor: "commitment:created" }),
    t("jordan", "invite", "invite", "Invite a friend: a private link, no contacts. It counts double for the hall."),
  ],
  staff: [
    start("staff", "This is what ScarletWell staff see: groups only, never a person.", "Aggregates only."),
    t("staff", "gaps", "staff-gaps", "Tap “Where supply is thin”.", { waitFor: "staff:gaps" }),
    t("staff", "narrow", "staff-narrow", "Now try to see a small group.", { waitFor: "staff:suppressed" }),
    t("staff", "ask", "staff-ask", "The database refused. Tap “Ask the data” for plain-English questions with the SQL shown."),
  ],
};

export const TOUR_ORDER: TourName[] = ["andre", "priya", "taylor", "sofia", "jordan", "staff"];
