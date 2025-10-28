export const formatWindowTime = (
  value: string | null | undefined,
): string => {
  if (!value) {
    return "—";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "—";
  }

  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};
