import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
export function reportRange(start: string, end: string) {
  const from = new Date(`${start}T00:00:00Z`),
    to = new Date(`${end}T00:00:00Z`);
  if (
    !Number.isFinite(+from) ||
    !Number.isFinite(+to) ||
    to < from ||
    (+to - +from) / 86400000 >= 366
  )
    throw Error("invalidRange");
  to.setUTCDate(to.getUTCDate() + 1);
  return { start: from.toISOString(), end: to.toISOString() };
}
export function initialRange() {
  const end = new Date();
  const start = new Date(end);
  start.setUTCDate(start.getUTCDate() - 6);
  return {
    from: start.toISOString().slice(0, 10),
    to: end.toISOString().slice(0, 10),
  };
}
