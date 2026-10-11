import type { Persona } from "../../demo/types";

/** How each synthetic student is introduced on the entry screen (our copy, not the API's demo notes). */
export const PERSONA_COPY: Record<Exclude<Persona, "staff">, { name: string; campus: string; line: string; story: string }> = {
  andre: {
    name: "Andre",
    campus: "Newark",
    line: "Newark commuter",
    story: "One gap between class and his afternoon job. Social is his growth area.",
  },
  priya: {
    name: "Priya",
    campus: "New Brunswick",
    line: "Busch sophomore",
    story: "Sleep is low. The reason is Calc II.",
  },
  taylor: {
    name: "Taylor",
    campus: "New Brunswick",
    line: "New Brunswick junior",
    story: "Emotional scores are very low. A person comes first.",
  },
  sofia: {
    name: "Sofia",
    campus: "Camden",
    line: "Camden grad student",
    story: "Works full time, prefers Spanish. Evenings and online only.",
  },
  jordan: {
    name: "Jordan",
    campus: "New Brunswick",
    line: "Livingston first-year",
    story: "Doesn't know anyone yet. Plays basketball.",
  },
};

export const PERSONA_ORDER: Exclude<Persona, "staff">[] = ["andre", "priya", "taylor", "sofia", "jordan"];
