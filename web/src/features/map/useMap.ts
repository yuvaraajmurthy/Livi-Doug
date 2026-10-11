import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "../../api/client";
import { language } from "../../i18n/useT";

/** The student's map; also keeps the UI language in step with the student's profile (Sofia reads Spanish). */
export function useMap(enabled = true) {
  const q = useQuery({ queryKey: ["map"], queryFn: api.map, enabled });
  const l = q.data?.student.language;
  useEffect(() => {
    if (l === "en" || l === "es") language.set(l);
  }, [l]);
  return q;
}
