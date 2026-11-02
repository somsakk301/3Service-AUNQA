import { useSearchParams } from "react-router-dom";

/** Optional ?curriculumCode= selector, passed through to the backend (contract TBD). */
export function useCurriculumCode() {
  const [params] = useSearchParams();
  const code = params.get("curriculumCode");
  return { code, search: code ? `?curriculumCode=${encodeURIComponent(code)}` : "" };
}
