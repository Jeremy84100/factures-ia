// Reuse the synchronous useSyncExternalStore version so shadcn's Sidebar never
// triggers an extra mount effect or desktop-to-mobile flash.
export { useIsMobile } from "./useMobile"
