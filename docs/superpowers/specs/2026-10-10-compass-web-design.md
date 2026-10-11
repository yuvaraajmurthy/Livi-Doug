# Compass web app and demo system: design

Date: 2026-10-10 · Status: draft for approval · Owner: this worktree (`ruhack/compass-backend`, branch `backend`)
Backend it targets: `https://d2fap8zqnl1gn5.cloudfront.net` (live, contract v1.1.0, `contract/openapi.json`)

## 1. What we are building and how we know it worked

A mobile-first React web app for students (and a desktop Staff Pulse) on top of the deployed Compass API, plus a
**demo system** that makes the whole product legible and convincing to judges in two settings:

- **Stage:** a 3-minute projected pitch, driven from a laptop by one presenter.
- **Table:** a judge holds a phone (theirs or ours) and taps through a short guided tour on their own.

Success, in order of importance:

1. A judge can say, unprompted, what Compass does for a student ("it turns my inventory score into one step that fits
   my week, follows up, and learns") and what staff get ("where supply is thin, without seeing anyone").
2. The stage demo cannot stall: every step works with the API live, with Bedrock off, with the database down
   (fixtures), and with no network at all (offline replay).
3. It looks like a product, not a hackathon page: minimal, calm, fast, and good on a 375 px phone.
4. Every claim on screen is backed by something live and inspectable (a real response time, real ranking weights,
   a real SQL query, a real push notification), and anything synthetic or mocked is labelled.

## 2. Context and constraints

- **Backend is done and live.** 36 operations; Andre/Priya/Taylor/Sofia/Jordan/staff personas; simulated clock with
  skip-ahead; reminders and follow-ups; memory; wins; challenges; Ask; staff aggregates with DB-enforced suppression;
  fixture fallback (`X-Compass-Fallback`); `POST /demo/force-templates` kill switch for AI.
- **Separate from `compass-chat`.** Another agent is building a chat-first app (`ruhack/compass-chat`, Strands, local
  Postgres). This app does not read, import or modify it. The user picks a winner.
- **Prior art reused, not copied.** The earlier frontend packet in `ruhack/docs/compass/frontend/` (claims ledger,
  honesty labels, Andre timeline) informed this design. Its contract audit predates the current backend and is stale.
- **Judge guidance (user-reported):** the judge who worked on the 18-question inventory cares about engagement and
  wellbeing: relevant and free events, campus resources, follow-ups, scores over time, and a profile/memory that
  improves personalisation. Her example: *low sleep → ask why → math homework → math tutoring*, not generic sleep tips.
  This is exactly Priya's path, so Priya gets a chapter in the main story.
- **Honesty rules** (carried from the backend): students and sample events are synthetic and labelled; The Arc is a
  mock; push works only where the browser allows it; scores change only with a new inventory take.
- **Time:** the event ends 2026-10-11. The plan is ordered so every checkpoint leaves a demoable app.

## 3. Decisions

| Decision | Choice | Why |
|---|---|---|
| Shape | Card-led app, Ask as a sheet | User choice. One next step is the product; chat is a helper. |
| Framework | React 19 + TypeScript + Vite | Fast build, static output, nothing server-side to break. |
| Routing | React Router 7 (library mode) | Deep links match backend `deep_link` values (`/plan/:id`, `/followup/:id`, `/next`). |
| Server state | TanStack Query 5 | Caching, retries, invalidate-on-clock-change in one place. |
| Styling | Tailwind CSS 4 with CSS-variable tokens | Fast to build a consistent system; tokens give light/dark. |
| Motion | `motion` (Framer Motion) | Springs, shared-layout card→plan transition, reduced-motion support. |
| Icons | Phosphor (`@phosphor-icons/react`), regular weight; fill only for the active tab | UI/UX skill default; one family. |
| Charts | Hand-written SVG components | Five small charts; no 100 KB library; full control of a11y. |
| Fonts | Geist (UI, tabular numbers) + Instrument Serif (display accents only), self-hosted via Fontsource | Modern and distinctive without hurting legibility; works offline. |
| Hosting | S3 + CloudFront via a new CDK stack `CompassWeb` in the same AWS account | One deploy command, HTTPS, same account as the API. CORS is already `*`. Vercel is the documented backup. |
| Location | `web/` in this worktree | One repo, one branch, fixtures shared with the backend. |
| Tests | Vitest + Testing Library (logic and components), Playwright (e2e and screenshots) | Screenshots also feed my own visual review. |

Rejected: Next.js (no server needed; static is safer on stage), a component kit like shadcn (we need only ~15 primitives
and a specific look), a map SDK in the core path (tiles are a network risk; map is optional, see §7.9).

## 4. Experience principles

1. **One thing per screen.** Each screen has one primary action. Everything else is subordinate or one tap away.
2. **Strengths first.** The map opens with what is going well. Low scores are "room to grow", never red alarms.
3. **Concrete over clever.** Time, place, cost, walk minutes, who else is going. Specifics are what persuade a
   student and a judge.
4. **Show the reasoning.** Every suggestion can explain itself with the actual ranking components and weights.
5. **Student stays in control.** Memory is listed with its source, can be deleted one by one or all at once.
6. **A person before an event** when the scores call for it (care-first), and a fixed crisis card when words do.
7. **Calm motion.** Motion explains cause and effect (card becomes plan; notification drops in; score bar grows).
   Nothing loops, nothing celebrates loudly. `prefers-reduced-motion` removes all non-essential motion.

## 5. Visual system

### 5.1 Tokens (light; dark variants defined alongside)

```css
:root {
  --bg: #F6F5F2;          /* warm paper canvas */
  --surface: #FFFFFF;
  --surface-2: #EFEEEA;   /* chips, wells */
  --ink: #15171A;         /* primary text, 16.9:1 on --bg */
  --ink-2: #565B63;       /* secondary text, 6.4:1 on --bg */
  --line: #E3E1DC;        /* decorative dividers */
  --line-strong: #8A8F96; /* control borders, 3.2:1 */
  --scarlet: #CC0033;     /* primary actions, focus accent; 5.6:1 on white */
  --scarlet-ink: #A3002A; /* scarlet text on tint */
  --scarlet-tint: #FBEAEE;
  --green: #1E7A52;       /* done states, always with text */
  --green-tint: #E7F3EC;
  --amber: #8A5A00;       /* uncertain hours/cost, sample labels */
  --amber-tint: #FBF1DC;
  --focus: #15171A;
  --radius-control: 12px; --radius-card: 20px; --radius-sheet: 28px;
  --shadow-float: 0 12px 32px -12px rgb(21 23 26 / 0.25);
}
@media (prefers-color-scheme: dark) { :root {
  --bg: #0F1012; --surface: #17191C; --surface-2: #1F2226; --ink: #F2F2F0; --ink-2: #A7ACB3;
  --line: #2A2E33; --line-strong: #6B7178; --scarlet: #FF4D6D; --scarlet-ink: #FF8FA3; --scarlet-tint: #3A1820;
  --green: #4CC38A; --green-tint: #15291F; --amber: #E8B34B; --amber-tint: #2E2410; --focus: #F2F2F0;
} }
```

Scarlet is Rutgers' colour, used sparingly: the one primary button per screen, the active tab, the focus accent.
It never marks a low score. Dimensions are distinguished by **icon and label**, not by eight colours.

### 5.2 Type

| Role | Font | Size / line | Weight |
|---|---|---|---|
| Display (entry, presenter slides, big numbers) | Instrument Serif | 40/44 (phone), 64/68 (stage) | 400 |
| Screen title | Geist | 28/34 | 600 |
| Card title | Geist | 20/26 | 600 |
| Body | Geist | 17/26 | 400 |
| Secondary | Geist | 15/22 | 400 |
| Meta / labels | Geist | 13/18 | 500 |

Numbers use `font-variant-numeric: tabular-nums`. Body never below 16 px on phones.

### 5.3 Shape, space, elevation

4-pt spacing (4, 8, 12, 16, 20, 24, 32, 48). Phone gutter 20 px (16 px under 360 px). Student content max-width 480 px,
centred on larger screens. Ordinary cards: 1 px `--line`, no shadow. The **hero step card** is the only element with
elevation on its screen. Sheets and the notification banner use `--shadow-float`.

### 5.4 Icons

Phosphor regular, 20 px inline / 24 px nav. Dimension icons: emotional `Heart`, environmental `Leaf`, financial
`Wallet`, intellectual `BookOpenText`, occupational `Briefcase`, physical `PersonSimpleRun`, social `UsersThree`,
spiritual `SunHorizon`. Decorative icons are `aria-hidden`; icon-only buttons have labels and tooltips.

### 5.5 Motion tokens

Press: scale 0.97, 100 ms. Enter: spring (stiffness 380, damping 32). Exit: 160 ms ease-in. Stagger: 40 ms.
Shared element: the step card morphs into the plan card (`layoutId`). Notification banner: drops from top with a
spring, auto-dismisses in 5 s, swipe or tap to dismiss. Reduced motion: opacity cross-fades only.

## 6. Information architecture

Student app (bottom tab bar, 4 items, icon and label):

| Tab | Route | Purpose |
|---|---|---|
| Today | `/next` | The one next step (or support first), alternates, Ask |
| Map | `/map` | Wellness map from the inventory: strengths first, history, change at retake |
| Campus | `/campus` | Cooperative challenges, anonymous wins wall, Ask |
| You | `/you` | Plans, what Compass knows (memory), language, notifications, privacy, forget me |

Other routes: `/` entry and persona picker · `/focus` choose-an-area flow · `/plan/:id` · `/followup/:id` · `/inbox` ·
`/i/:token` friend invite (no login) · `/card` MyRutgers card preview · `/staff/*` Staff Pulse · `/present` stage mode ·
`/tour` and `/tour/:persona` table mode · `/join?t=` attach a device to an existing session.

The top bar carries the page title, the inbox bell (badge = unread), and in demo builds a **clock pill**
(`Mon Oct 12 · 9:00 AM`) that opens the time sheet (§9.5).

## 7. Screens (student)

Every screen has four designed states: loading (skeleton matching final layout), ready, empty, error (cause + retry).
Fallback responses (`X-Compass-Fallback: fixture`) render normally with a small "Demo data" chip in the clock pill.

### 7.1 Entry `/`

Serif headline "One next step from your Wellness Inventory." Persona list as large rows (name, campus, one-line
situation, synthetic tag). Secondary links: "Present (stage)", "Take the tour", "Staff Pulse". Picking a persona calls
`POST /demo/session` and routes to `/next` (or `/focus` if no focus is set yet).

### 7.2 Focus flow `/focus` (three short steps, progress dots, back always works)

1. **Your strengths** (from `/me/map`): "From your inventory on Sep 14". Two strength rows animate in first, then a
   quiet "Room to grow" pair. One button: "Choose one area to work on".
2. **Pick one area:** 8 dimension chips, growth areas pre-highlighted (not pre-selected). One choice.
3. **What gets in the way?** Barrier chips from `/meta/barriers` (multi-select, en/es), plus an optional
   "In your own words" field (140 chars, helper text says it is checked for safety and not stored).
   Submit → `POST /me/focus`.
   - `kind: crisis` → crisis screen (§7.6) replaces the flow.
   - `support` present → care-first Today (§7.5).
4. **Finding your step** (the wait, ~1.4 s): a three-line checklist that ticks as the request resolves:
   "Checking your free windows", "Ranking {N} Rutgers events and services" (N from the trace header, §11.2),
   "Keeping it free and on your campus". Then the hero card animates in on Today.

### 7.3 Today `/next`

- Greeting line ("Monday, Andre") and focus chip ("Growing: Social · change").
- **Hero step card:** sample/source badge, title, `when_label`, `window_label` ("Fits your Tuesday gap, 12:20–2:30",
  green check icon), venue + walk minutes, cost, `going.label`, rung chip ("Structured: you'll be doing something,
  not mingling"), the one-sentence `why`. Primary "I'm in". Secondary "Not for me".
- **Why this fits** (sheet): filter checks as a list; ranking components as five horizontal bars with weight and score
  (e.g. "Fits your schedule · 20%"), memory facts used ("You enjoyed game-based events"), distance, total. Footer:
  "Code chose this step from fixed weights. AI only wrote the sentence." (`why_source` shown as "AI wording" or
  "Template wording").
- **Not for me:** one-tap reasons (time, place, not my thing, other) → `POST /me/next/{rec_id}/decline` → next card
  slides in.
- **Two other options**: compact rows under the hero; tapping one opens it as a hero.
- **Ask Compass** pill at the bottom of the scroll → Ask sheet (§7.11).
- Retake nudge card when `retake_nudge.show` and no plan is pending.

### 7.4 Plan `/plan/:id`

After `POST /commitments` the hero card morphs into the plan card. Content: the implementation-intention sentence
(`plan_text`, large), when/where, reminder time ("We'll remind you at 12:15"), and three actions:
"Add to calendar" (ICS download or Google link), "Invite a friend" (Web Share API with `share_text` + invite URL,
copy-link fallback), "Turn on reminders" (push permission is requested here, in context, never on first load).
When the invite is accepted (Compass never sees contacts, so no name): "Your friend said they'll come · counts double
for the Newark Cup".

### 7.5 Care-first Today (Taylor)

`support_card` renders first, full width: title, message, options as rows with Call / Open buttons, address, hours.
Events are not shown by default; a quiet link "Prefer something small to do?" reveals the picks (backend already sets
`pushed: false` for these). No "I'm in" pressure on this screen.

### 7.6 Crisis screen

Full-screen, calm, no animation beyond a fade. Title and message from the response; each line is a large
call/text button (`href` = `tel:`/`sms:`) with hours. Unverified lines show "Verifying" (not hidden). A clear
"Back to Compass" at the bottom. Nothing the student typed is echoed.

### 7.7 Inbox `/inbox` and notification banner

Inbox lists `/me/inbox` items newest first with kind icon, title, body, time; tap → deep link. When skip-ahead returns
`fired` items, each one drops in as a banner styled like a system notification (app icon, "Compass", "now", title,
body). Real Web Push also fires on subscribed devices (§9.6).

### 7.8 Follow-up `/followup/:id`

Two taps: "Did you go?" (Yes / No / Didn't happen) then "Did it help?" (1–5, labelled ends). Submit →
`POST /followups/{id}`. Result screen, revealed in sequence (each line fades up, 120 ms apart):

1. Check + "1 step taken this month. That counts."
2. "Wellness credit added to The Arc (demo)".
3. Newark Cup bar animates from old to new progress ("+2, you brought a friend").
4. "What Compass learned": the `learned` facts as memory rows with source ("You rated … 4/5") and a delete icon.
5. Next rung message.
6. If `win_prompt`: "Share a small win anonymously?" text field → `POST /wins` (crisis-checked).

"Went: no" gets a neutral, guilt-free result ("No problem. Want something easier next time?").

### 7.9 Map `/map`

Header "Your wellness map · from the inventory on {taken_on}". Eight rows sorted by score (strengths first): icon,
label, score (tabular), band word, a thin bar on a shared 1–4 scale, blurb. With previous takes, each row gets a
change marker ("↑ 0.5 since Sep 14") and a tiny history line on tap. A note: "Scores come from the inventory. Compass
never changes them; your next retake does." Below: "Steps you've taken" (activity, separate from scores).
Optional (P2): a small campus map of the next step's venue using MapLibre + OpenFreeMap tiles, lazy-loaded, with a
plain address fallback.

### 7.10 Campus `/campus`

- **Challenges:** each as a card with scope ("Newark"), goal, progress bar, dates, and the rule line
  ("Cooperative: each campus races its own goal… No individual leaderboard").
- **Wins wall:** anonymous short posts with dimension icon and campus; "Same here" button with count
  (`POST /wins/{id}/same-here`, optimistic).
- Ask pill.

### 7.11 Ask sheet

Bottom sheet with one input ("Ask about Rutgers events and resources"), three suggestion chips, answer text, and item
rows (title, when, where, link/phone). Crisis responses replace the sheet content with the crisis card. Shows
"Answers only about Rutgers resources" under the input. `POST /ask`.

### 7.12 You `/you`

Sections: My plans (upcoming/past with status), **What Compass knows** (`/me/memory`: statement, source label, "used
for", delete per row, "Delete all"), Language (en/es, from profile; UI chrome switches), Notifications (push on/off),
"MyRutgers card" preview link, and, separated at the bottom, "Forget me" (confirm dialog → `DELETE /me`).

### 7.13 Friend invite `/i/:token` (public)

No tab bar. "Your friend thought you might like this. No account needed." Event card, going count, "I'll come"
(`POST /invites/{token}`) → "You're in. See you there."

### 7.14 MyRutgers card `/card`

A neutral portal mock (no Rutgers marks) labelled "Illustration: how Compass sits inside MyRutgers", showing the
`/me/card` tile (title, when, one line, "Open Compass").

## 8. Staff Pulse `/staff`

Desktop-first, responsive to phone (sections stack, charts get table equivalents). Left rail: Overview, Gaps,
Trends, Ask the data. Header shows "Synthetic semester · as of {now} · groups under 10 hidden by the database".

- **Overview:** four figures (students reached, took a step, attended, said it helped) and a funnel by campus from
  `/staff/funnel`. Filters: campus, dimension, level, first-gen, housing.
- **Gaps:** "Where supply is thin": bars of `low_students_per_item` by campus × dimension from `/staff/gaps`, with a
  callout card generated from the top Camden row ("Camden financial: 20.5 students with low financial scores per
  resource. Newark: 14.9."). Phrase it as a within-Camden gap, per the earlier decision.
- **Trends:** weekly average for one chosen dimension (`/staff/weekly`), midterms band shaded and labelled, dips from
  `/staff/dips` marked with their drop and n. Retakes: users vs non-users retake rate per campus (`/staff/retakes`).
- **Suppression made visible:** a row "{suppressed_groups} groups hidden (fewer than 10 students)" and a "Try to see a small group"
  button that applies a narrow filter; hidden cells render as hatched "Under 10" (never zero, never a number).
- **Ask the data:** question → answer, the generated SQL in a monospace block, and the result table (`/staff/ask`).

## 9. Demo system

One **story script** (TypeScript data) drives both stage and table modes. Each step declares what screen it shows, what
action it performs, the claim it makes, the live proof it surfaces, and the presenter note.

### 9.1 Story script shape

```ts
type StoryStep = {
  id: string;
  chapter: string;                 // "Andre: one step that fits"
  persona: Persona | null;         // null = presenter slide
  route?: string;                  // where the app should be
  target?: string;                 // data-tour id to spotlight, e.g. "im-in"
  perform?: Action;                // what "Next" does for the presenter: tap target, type text, skip time, set clock
  waitFor?: Signal;                // event that completes the step, e.g. "commitment:created"
  claim: string;                   // one sentence shown on the stage rail / coach bar
  proof?: ProofKind;               // which live evidence panel to show (fit, latency, safety, memory, sql, push, ...)
  note?: string;                   // presenter-only speaking note
  tag?: "Impact" | "Engagement" | "Safety" | "Equity" | "Feasibility" | "Privacy";
};
```

### 9.2 The main story (stage, about 3 minutes)

| # | Chapter | What happens | Claim on the rail |
|---|---|---|---|
| 0 | Cold open (slide) | "1,505 students took the inventory. Then what?" Plain results-page illustration with "Social 1.9" and nothing to do. | A score alone doesn't change a week. |
| 1 | Andre | Strengths reveal, pick Social, tap "No time" + "I don't know anyone". | Strengths first; he chooses. |
| 2 | One step | Finding checklist → hero card: Commuter lunch, Tue 12:30, fits his gap, free, 14 going. Open "Why this fits". | Code ranks with fixed weights; AI only words it. |
| 3 | Plan | "I'm in" → plan sentence, calendar, invite, reminders on. | If-then plans make follow-through more likely. |
| 4 | Follow-through | Skip time → 12:15 reminder drops in (and buzzes the paired phone). Skip → follow-up; Yes, 4/5. Arc credit, Newark Cup, learned facts, next rung. | It follows up and learns, with the student's say. |
| 5 | Next week | Clock to Oct 19 → basketball Thu 12:30, rung 3, reason cites "You enjoyed game-based events". Delete one memory fact. | Memory is visible and deletable. |
| 6 | Retake | Clock to Oct 27 → Map: Social 1.9 → 2.4, labelled as the retake. | Scores over time, honestly attributed. |
| 7 | Priya | Physical low; she types "Calc II problem sets keep me up till 2" → Busch Learning Center tutoring. | Ask why, fix the cause: your sleep → math example. |
| 8 | Taylor + safety | Taylor: a person first. Then type a crisis phrase in Ask → fixed crisis card; rail shows "Caught by code in N ms. No AI saw it." | Safety is code-first. |
| 9 | Staff | Camden financial gap; hidden small groups; Ask the data with SQL shown. | Staff see where to act, never who. |
| 10 | Close (slide) | Measured numbers, architecture line, pilot ask, QR "Try it on your phone". | Ready for a spring pilot. |

Optional chapters (feature atlas, for Q&A): Sofia (Camden, Spanish, online evening), Jordan (residence-hall
challenge, friend invite accepted), Pull the plug on AI, Offline, MyRutgers card, Forget me.

### 9.3 Stage mode `/present`

Layout at 1280×720 and up: left, a phone frame with an **iframe of the real app** at 390×844 (scaled to fit), so media
queries and behaviour are the true mobile ones; right, the **rail**:

- Chapter title (serif, large) and the claim.
- **Proof panel** for the step: fit bars, safety pipeline with timing, memory facts with sources, SQL, the funnel, or
  the push receipt.
- **Live request log**: the last 4 API calls (`GET /me/next · 212 ms · live`), fed from the iframe via
  `postMessage`. Fallback calls show `fixture` in amber.
- Tag chip (Impact / Safety / Equity …) so judges can map what they see onto their score sheet.
- Footer: chapter dots, elapsed time against 3:00, clock pill, mode badge (Live / Templates / Offline).

Keyboard: `→`/`Space` next (performs the step's action in the iframe), `←` back, `N` notes, `P` pair phone (QR),
`A` AI on/off (calls force-templates), `O` offline replay on/off, `R` reset story (confirm; calls `POST /demo/reset`
only on the stage session), `F` fullscreen, `1–9` jump to chapter.

"Perform" means the presenter never fumbles: pressing Next taps the target inside the app (with a visible tap
ripple), types text with a typewriter effect, or moves the clock. The presenter can also click the phone directly.

Slides (cold open, close) are full-width rail content with the phone hidden.

### 9.4 Table mode `/tour`

Phone-first. Landing: "Try Compass as…" with five persona cards and Staff. Each opens a **sandbox session** (§11.1)
so concurrent judges never collide. A **coach bar** sits above the tab bar: "Step 2 of 6 · Tap I'm in", with
Back, Skip and Exit. The current target gets a spotlight (dimmed surroundings, focus ring, never blocks other UI
from screen readers). Time-travel steps show a "Skip ahead →" button in the coach bar. Tours are 5–7 steps, 60–90
seconds. A completion card summarises what they just did ("One step, planned, followed up. Compass learned 3
things.") and offers the next tour and the staff view.

### 9.5 Time sheet (all demo modes)

Opened from the clock pill: current simulated time, "Skip to next reminder" (`skip-ahead next_due`), "+1 day",
preset jumps (Tue 12:15, Tue 3:30 PM, Mon Oct 19, Tue Oct 27), and Reset (stage only). Changing time invalidates all
queries; fired notifications appear as banners.

### 9.6 Phone pairing and real push

Stage: `P` shows a QR to `/join?t=<stage token>`. The presenter's phone opens the same session, enables reminders,
and receives the real Web Push when the laptop skips time. Android Chrome works in the browser; iPhone requires the
app to be added to the Home Screen (PWA manifest + service worker included). The in-app banner always shows, so the
story never depends on push delivery. Push receipt shows in the proof panel when the service worker reports it.

### 9.7 Offline replay

A `ReplayTransport` answers API calls from (a) a recorded run of the main story captured from production and (b) the
backend's per-persona fixtures. `O` switches to it; it also engages automatically if three consecutive requests fail.
The mode badge says "Offline replay", and the request log marks responses `replay`. A recorder
(`npm run record-story`) re-captures the story from the live API on demand.

## 10. Why this persuades (and stays honest)

| Principle | Where it appears |
|---|---|
| Problem before solution (contrast) | Cold open shows today's dead-end results page before Compass. |
| One identifiable person | Andre's specifics: commuter, 12:20–2:30 gap, eats in his car, works at 3. |
| Speak to the judge's own example | Priya's chapter is the judge's sleep → math → tutoring story. |
| Show, don't claim | Each claim is paired with live proof (timings, weights, SQL, push receipt). |
| Close an open loop | The story opens on an unfinished loop (score, no action) and closes it (step, follow-up, retake). |
| Peak, then a strong end | Peak: the phone buzzes / "What Compass learned". End: staff decision + pilot ask, left on screen during Q&A. |
| Reduce perceived risk | Crisis handled by code live; AI switched off live; DB-enforced privacy; it plugs into MyRutgers, the Wellness Calendar, CAPS, The Arc. |
| Let them do it (ownership) | Table mode puts the phone in the judge's hand; QR on the closing slide. |
| Processing fluency | Minimal UI, one action per screen, large type: simple to read reads as well-built. |
| Evidence-based behaviour design | Rail notes cite implementation intentions (Gollwitzer & Sheeran 2006, meta-analysis of 94 studies, d≈0.65), fresh-start timing (Dai, Milkman & Riis 2014), graded social steps (rungs), cooperative not competitive challenges. |
| Make scoring easy | Tag chips map each chapter to a likely criterion; the close slide lists evidence per criterion. |

Claims that are never made: that Compass improved real students' wellbeing; that sample events are real; that The Arc
is connected; that push works on every phone; that one event raised a score.

## 11. Backend changes required

### 11.1 Sandbox sessions (for table mode)

`POST /demo/session {"persona":"andre","sandbox":true}` issues a token whose sid starts with `sb`, and clones the
persona's rows (students, profiles, consents, inventory_takes, dimension_scores, student_memory) to
`DEMO-ANDRE~<sid>`, flagged `students.sandbox = true`. `SessionCtx.student_id` returns the clone id for `sb` sids
(the sid is inside the signed token, so it cannot be forged). Staff functions exclude sandbox students. `/demo/reset`
deletes all sandbox students. Clones older than 6 hours are deleted by the dispatcher loop. Fixture fallback still
works (fixtures are keyed by persona).

### 11.2 Trace header

`X-Compass-Trace` on student routes, exposed via CORS: compact `key=value;…` with `safety=lexicon|model|none`,
`safety_ms`, `candidates` (items considered), `passed` (after hard filters), `rank_ms`, `wording=ai|template|cache`.
No free text, no scores. Feeds the finding checklist and the stage proof panels truthfully.

### 11.3 Encoding fixes

Spanish barrier labels come back double-encoded ("lo mÃ­o") from `/meta/barriers`, and several recorded fixtures
contain mojibake ("12:30â€“1:30"). Fix the source files, re-record the fixtures, and add a test that rejects
`Ã`/`â€` sequences in any fixture or YAML.

### 11.4 Priya wording

Her pick's `why` reads awkwardly ("…fits because it's an in-person Rutgers Learning Centers resource for coursework").
Add a root-cause template line ("Free drop-in math tutoring at Busch, so Calc II stops eating your nights") and
re-prewarm, so both AI and template paths read well.

## 12. Frontend architecture

```
web/
  index.html, vite.config.ts, public/ (manifest, icons, sw.js)
  src/
    main.tsx, app/routes.tsx, app/providers.tsx
    api/       transport.ts (Live | Replay), client.ts (typed calls), types.ts (generated from contract), inspector.ts (event bus)
    session/   session.ts (token, persona, sandbox, join), clock.ts (sim now store)
    i18n/      en.ts, es.ts, useT.ts
    ui/        Button, Chip, Card, Sheet, Badge, Skeleton, Banner, TabBar, TopBar, ClockPill, ProgressBar, Bars, Spark, EmptyState, ErrorState, Dialog
    features/  entry/, focus/, today/, plan/, followup/, inbox/, map/, campus/, ask/, you/, invite/, card/, staff/, safety/
    demo/      story.ts, tours.ts, engine.ts (reducer), coach/, present/, replay/ (recording.json, fixtures index), pair/
    push/      push.ts (subscribe, receipt)
  tests/       unit + component (Vitest), e2e (Playwright)
```

- **Types** are generated from `contract/openapi.json` with `openapi-typescript`, so the app breaks at compile time if
  the contract drifts.
- **Transport** wraps `fetch` with base URL, bearer token, 8 s timeout, one retry for GETs, and emits
  `{method, path, ms, status, fallback, trace, requestId}` on the inspector bus.
- **Query keys** `['map']`, `['next']`, `['inbox']`, `['memory']`, `['pulse']`, `['staff', name, filters]`. Any response
  whose `now` differs from the clock store updates it and invalidates student queries.
- **Mutations** (commit, follow-up, decline, wins) disable their button while pending and are not retried
  automatically; a timeout shows "That didn't go through. Try again." with the state unchanged.
- **Demo engine** is a pure reducer over the story script: `(state, event) → state`, unit-tested without React. The
  app emits signals (`commitment:created`, `followup:submitted`, `crisis:shown` …) through the inspector bus; the
  coach bar and the stage rail subscribe.
- **Stage ↔ iframe** messages: `perform`, `signal`, `request-log`, `navigate`. Same-origin only.

## 13. Resilience matrix

| Failure | What the audience sees | Mechanism |
|---|---|---|
| Bedrock slow or down | Same flow; wording from templates; badge "Templates" if forced | Backend templates + `A` switch |
| Database down | Same flow on recorded data; "Demo data" chip | Backend fixture fallback |
| API/CloudFront unreachable | Same story continues; "Offline replay" badge | `ReplayTransport` (auto after 3 failures, or `O`) |
| Push denied/unsupported | Banner still drops in | In-app banner always shown |
| Venue Wi-Fi blocks fonts/tiles | Nothing (fonts self-hosted; map optional) | Bundled assets |
| Concurrent judges | Each in their own sandbox | §11.1 |
| Presenter mis-click | Back (`←`) restores the previous step; `1–9` jumps | Story reducer checkpoints |

## 14. Accessibility and performance budgets

WCAG 2.2 AA: contrast as in §5.1, visible focus (2 px ink ring, 3 px offset), 44×44 touch targets, labels on all
inputs, live region for state changes and banners, focus moved to the heading on route change, sheets and dialogs trap
focus and close with Escape, spotlight never removes content from the accessibility tree. Works at 320 px and at 200%
text size. Reduced motion respected everywhere.

Budgets: initial JS ≤ 180 KB gzip for the student app (staff, present and MapLibre are lazy chunks); LCP ≤ 1.5 s on a
mid phone over 4G from CloudFront; no layout shift from async content (skeletons match final size).

## 15. Testing and acceptance

- Unit: demo reducer (every step reachable, back restores, guards), transport (timeouts, fallback flag, replay
  matching), formatters, i18n completeness (every key in en exists in es).
- Component: hero card, why sheet, follow-up result, crisis screen, memory list, staff suppression rendering, with
  MSW serving the backend fixtures.
- E2E (Playwright, phone 390×844 and stage 1280×720): the full Andre story on a sandbox session against production;
  Taylor care-first; crisis in focus text and in Ask; staff suppression; offline replay story with network blocked.
- Visual review: screenshots of every screen in light and dark at 375 px, read and critiqued before sign-off.
- Acceptance: the stage story runs end to end three times in a row with no manual recovery; once with AI forced
  off; once in offline replay. Table tours complete on a real phone.

## 16. Out of scope and limits

No real login (demo tokens), no real MyRutgers embedding, no real Arc connection, no native app, no editing of
schedules (free windows come from the seeded profile), no new questionnaire. Map is optional (P2). Push on iPhone
requires Home Screen install.

## 17. Risks

| Risk | Mitigation |
|---|---|
| Time: the event ends tomorrow | Plan ordered so each checkpoint is demoable; stage story before table polish; P2 last. |
| AWS session credentials expire | Deploy web early; Vercel backup documented; offline replay runs from any static host or `npm run preview`. |
| Judge's phone is an iPhone (no push) | Banner always shows; push shown on our paired Android or installed PWA. |
| Presenter on an unfamiliar projector | Stage layout tested at 1280×720 and 1920×1080; `F` fullscreen; font sizes for the back row. |
| Other agent changes shared files | This app lives only in `compass-backend/web` and backend changes stay on this branch. |
