import { COLOR_STATUS_GREEN, COLOR_STATUS_YELLOW, COLOR_STATUS_RED } from "../constants/colors";

export const resolveSuccessColor = (percent: number): string => {
  if (percent < 80) {
    return COLOR_STATUS_RED;
  }
  if (percent >= 90) {
    return COLOR_STATUS_GREEN;
  }
  return COLOR_STATUS_YELLOW;
};

export default resolveSuccessColor;
