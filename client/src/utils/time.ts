export const formatWindowTime = (
  value: string | null | undefined,
  hour12?: boolean | null,
): string => {
  if (!value) {
    return "—";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "—";
  }

  const opts: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit" };
  if (hour12 === true) opts.hour12 = true;
  if (hour12 === false) opts.hour12 = false;
  return parsed.toLocaleTimeString([], opts as any);
};

// Returns true when 24-hour time should be used, false when 12-hour time should be used.
// Reads localStorage key 'pref_time_24h' where '1' => prefer 24h, '0' => prefer 12h, missing => Auto.
export const use24hTime = (): boolean => {
  try {
    const v = localStorage.getItem('pref_time_24h');
    if (v === '1') return true;
    if (v === '0') return false;
  } catch {
    // ignore and fall back to detection below
  }

  // Auto: detect system preference (return true for 24h, false for 12h)
  try {
    const sample = new Date(2020, 0, 1, 23, 0, 0).toLocaleTimeString(undefined, { hour: 'numeric', minute: 'numeric' });
    const ampmPattern = /\bAM\b|\bPM\b|am|pm|午前|午後|오전|오후/;
    if (ampmPattern.test(sample)) return false; // system uses 12h -> return false (not 24h)
    if (/\b23\b|\b13\b/.test(sample)) return true; // likely 24h
    const ro = new Intl.DateTimeFormat(undefined, { hour: '2-digit' }).resolvedOptions();
    return !(ro && ro.hour12);
  } catch {
    // conservative default: prefer 24h
    return true;
  }
};
