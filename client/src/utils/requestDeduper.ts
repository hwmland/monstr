type LastCall = { time: number };

const normalizeSelectionKey = (selection: string[]) => {
  return selection.length ? JSON.stringify([...selection].slice().sort()) : "__ALL__";
};

export const createRequestDeduper = () => {
  const calls = new Map<string, LastCall>();
  const inFlight = new Map<string, Promise<any>>();

  // Accepts a selection array. If the selection is not a duplicate within
  // `windowMs`, the call will be recorded.
  const isDuplicate = (selection: string[], windowMs = 1000) => {
    const key = normalizeSelectionKey(selection);
    const now = Date.now();
    const last = calls.get(key);
    if (last && now - last.time < windowMs) {
      return true;
    }
    // record non-duplicate automatically to make callers simpler
    calls.set(key, { time: now });
    return false;
  };

  const record = (selection: string[]) => {
    const key = normalizeSelectionKey(selection);
    calls.set(key, { time: Date.now() });
  };

  // Coalesce concurrent requests for the same selection so callers share the
  // same in-flight promise instead of re-invoking the underlying function.
  // The provided `fn` is executed only if there is no existing in-flight
  // promise for the same selection. When the promise settles, the call time
  // is recorded so subsequent rapid calls can still be considered duplicates
  // by `isDuplicate` if desired.
  const coalesce = async <T>(selection: string[], fn: () => Promise<T>): Promise<T> => {
    const key = normalizeSelectionKey(selection);
    const existing = inFlight.get(key) as Promise<T> | undefined;
    if (existing) {
      return existing;
    }

    const promise = (async () => {
      try {
        const result = await fn();
        return result;
      } finally {
        // mark the time of completion so future calls can be
        // treated as duplicates by `isDuplicate` if callers use that API.
        calls.set(key, { time: Date.now() });
        inFlight.delete(key);
      }
    })();

    inFlight.set(key, promise as Promise<any>);
    return promise;
  };

  return { isDuplicate, record, coalesce };
};

export default createRequestDeduper;
