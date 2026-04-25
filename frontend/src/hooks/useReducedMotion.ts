import { useReducedMotion as fmUseReducedMotion } from "framer-motion";

/**
 * Wrapper around framer-motion's `useReducedMotion` so the rest of the app
 * imports a single, project-owned hook (lets us swap implementations later
 * without touching consumers).
 */
export function useReducedMotion(): boolean {
  return fmUseReducedMotion() === true;
}
