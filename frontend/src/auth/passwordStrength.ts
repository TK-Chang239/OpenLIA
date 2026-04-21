export type StrengthLevel = 0 | 1 | 2 | 3 | 4;

export function passwordStrength(pw: string): StrengthLevel {
  if (pw.length === 0) return 0;
  if (pw.length < 8) return 1;

  let classes = 0;
  if (/[a-z]/.test(pw)) classes += 1;
  if (/[A-Z]/.test(pw)) classes += 1;
  if (/[0-9]/.test(pw)) classes += 1;
  if (/[^a-zA-Z0-9]/.test(pw)) classes += 1;

  if (classes >= 4) return 4;
  if (classes === 3) return 3;
  return 2;
}
