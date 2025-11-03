export type RateUnit = "bps" | "Kbps" | "Mbps";
export type SizeUnit = "B" | "KB" | "MB" | "GB";

type UnitDefinition<T extends string> = {
  unit: T;
  factor: number;
};

const RATE_UNITS: ReadonlyArray<UnitDefinition<RateUnit>> = [
  { unit: "bps", factor: 1 },
  { unit: "Kbps", factor: 1_000 },
  { unit: "Mbps", factor: 1_000_000 },
];

const SIZE_UNITS: ReadonlyArray<UnitDefinition<SizeUnit>> = [
  { unit: "B", factor: 1 },
  { unit: "KB", factor: 1024 },
  { unit: "MB", factor: 1024 ** 2 },
  { unit: "GB", factor: 1024 ** 3 },
];

const normalizePositive = (value: number): number => {
  return Number.isFinite(value) && value > 0 ? value : 0;
};

export const pickRateUnit = (bitRate: number): UnitDefinition<RateUnit> => {
  const safeRate = normalizePositive(bitRate);

  for (const candidate of RATE_UNITS) {
    const candidateValue = safeRate / candidate.factor;
    if (candidateValue >= 1 && candidateValue < 1_000) {
      return candidate;
    }
  }

  const largest = RATE_UNITS[RATE_UNITS.length - 1];
  if (safeRate >= largest.factor) {
    return largest;
  }

  return RATE_UNITS[0];
};

export const pickRatePresentation = (
  bitRate: number,
): { value: number; unit: RateUnit } => {
  const unit = pickRateUnit(bitRate);
  const safeRate = normalizePositive(bitRate);
  return { value: safeRate / unit.factor, unit: unit.unit };
};

export const formatRateValue = (value: number): string => {
  if (value === 0) {
    return "0.00";
  }
  if (value >= 100) {
    return value.toFixed(1);
  }
  return value.toFixed(2);
};

export const pickSizeUnit = (bytes: number): UnitDefinition<SizeUnit> => {
  const safeBytes = normalizePositive(bytes);

  for (const candidate of SIZE_UNITS) {
    const candidateValue = safeBytes / candidate.factor;
    if (candidateValue >= 1 && candidateValue < 1024) {
      return candidate;
    }
  }

  const largest = SIZE_UNITS[SIZE_UNITS.length - 1];
  if (safeBytes >= largest.factor) {
    return largest;
  }

  return SIZE_UNITS[0];
};

export const pickSizePresentation = (
  bytes: number,
): { value: number; unit: SizeUnit } => {
  const unit = pickSizeUnit(bytes);
  const safeBytes = normalizePositive(bytes);
  return { value: safeBytes / unit.factor, unit: unit.unit };
};

export const formatSizeValue = (value: number): string => {
  if (!Number.isFinite(value) || value === 0) {
    return "0.0";
  }
  if (value >= 100) {
    return value.toFixed(1);
  }
  return value.toFixed(2);
};
