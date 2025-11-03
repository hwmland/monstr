export const SATELLITE_ID_TO_NAME: Record<string, string> = {
  "1wFTAgs9DP5RSnCqKV1eLf6N9wtk4EAtmN5DpSxcs8EjT69tGE": "Saltlake",
  "121RTSDpyNZVcEU84Ticf2L1ntiuUimbWgfATz21tuvgk3vzoA6": "AP1",
  "12EayRS2V1kEsWESU9QMRseFhdxYxKicsiFmxrsLZHeLUtdps3S": "US1",
  "12L9ZFwhzVpuEKMUNUqkaTLGzwY9G24tbiigLiXpmZWKwmcNDDs": "EU1"
};

export const translateSatelliteId = (satelliteId: string | undefined | null): string => {
  if (!satelliteId) {
    return "";
  }

  return SATELLITE_ID_TO_NAME[satelliteId] ?? satelliteId;
};
