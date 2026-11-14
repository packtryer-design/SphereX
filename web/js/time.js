// Dates for observations. SPHEREx times are MJD (days); show them as plain UTC dates.
const DAY_MS = 86_400_000;
const MJD_UNIX_EPOCH = 40587;

export const mjdToDate = (mjd) => new Date((mjd - MJD_UNIX_EPOCH) * DAY_MS);
const fmt = (mjd, opts) => mjdToDate(mjd).toLocaleDateString("en-GB", { timeZone: "UTC", ...opts });

export const formatDate = (mjd) => fmt(mjd, { day: "numeric", month: "short", year: "numeric" });
export const formatMonth = (mjd) => fmt(mjd, { month: "short", year: "numeric" });

// "6–17 Sep 2025", "28 Sep – 4 Oct 2026", "20 Dec 2025 – 3 Jan 2026"
export function formatRange(a, b) {
  const da = mjdToDate(a), db = mjdToDate(b);
  const y = (d) => d.getUTCFullYear(), m = (d) => d.getUTCMonth();
  if (Math.floor(a) === Math.floor(b)) return formatDate(a);
  if (y(da) === y(db) && m(da) === m(db)) return `${da.getUTCDate()}–${formatDate(b)}`;
  if (y(da) === y(db)) return `${fmt(a, { day: "numeric", month: "short" })} – ${formatDate(b)}`;
  return `${formatDate(a)} – ${formatDate(b)}`;
}

export function formatGap(days) {
  if (days < 1.5) return "1 day";
  if (days < 14) return `${Math.round(days)} days`;
  if (days < 60) return `${Math.round(days / 7)} weeks`;
  const months = Math.round(days / 30.44);
  return months === 1 ? "1 month" : `${months} months`;
}
