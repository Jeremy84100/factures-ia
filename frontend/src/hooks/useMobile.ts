import { useSyncExternalStore } from "react"

const QUERY = "(max-width: 767px)"

const subscribe = (onChange: () => void) => {
  const mql = window.matchMedia(QUERY)
  mql.addEventListener("change", onChange)
  return () => mql.removeEventListener("change", onChange)
}

// Read synchronously on the first render: a phone never renders the desktop
// layout first, so nothing jumps when the page opens.
export function useIsMobile() {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false,
  )
}
