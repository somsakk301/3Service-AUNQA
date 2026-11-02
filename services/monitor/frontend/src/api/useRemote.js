import { useCallback, useEffect, useState } from "react";

/** How often a page asks the backend again for the newest result (GET only). */
export const RETRY_MS = 10_000;

/**
 * Remote state: { state: "loading" } | { state: "error", status, checkedAt } | { state: "done", data, checkedAt }
 * (`status` is the HTTP status of a failed request, or null when the backend could not be reached.)
 * `retryWhile(remote)`: when it returns true for a settled state, the same GET is sent again after
 * RETRY_MS, without going back to "loading", until it returns false or the page is left.
 * `reload()`: send the same GET now, also without going back to "loading" (e.g. after a verification was saved).
 */
export function useRemote(load, deps, { retryWhile } = {}) {
  const [remote, setRemote] = useState({ state: "loading" });
  const depsKey = JSON.stringify(deps);
  const [retry, setRetry] = useState({ key: depsKey, n: 0 });
  if (retry.key !== depsKey) setRetry({ key: depsKey, n: 0 }); // new deps: start over (React-supported render-time update)
  const attempt = retry.key === depsKey ? retry.n : 0;

  useEffect(() => {
    const ctrl = new AbortController();
    let timer;
    if (attempt === 0) setRemote({ state: "loading" });
    const settle = (next) => {
      setRemote(next);
      if (retryWhile?.(next)) timer = setTimeout(() => setRetry((r) => ({ ...r, n: r.n + 1 })), RETRY_MS);
    };
    load(ctrl.signal).then(
      (data) => settle({ state: "done", data, checkedAt: new Date() }),
      (err) => {
        if (ctrl.signal.aborted) return;
        console.error("[Mornitor] could not load monitoring data:", err); // for developers; the page shows a plain message
        settle({ state: "error", status: err?.status ?? null, checkedAt: new Date() });
      },
    );
    return () => {
      ctrl.abort();
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [depsKey, attempt]);
  const reload = useCallback(() => setRetry((r) => ({ ...r, n: r.n + 1 })), []);
  return { ...remote, reload };
}
