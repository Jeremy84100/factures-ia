import { useState } from "react"

export function useCopyToClipboard(): [
  string | null,
  (text: string) => Promise<boolean>,
] {
  const [copiedText, setCopiedText] = useState<string | null>(null)

  const copy = async (text: string) => {
    if (!navigator?.clipboard) return false
    try {
      await navigator.clipboard.writeText(text)
      setCopiedText(text)
      window.setTimeout(
        () => setCopiedText((current) => (current === text ? null : current)),
        2000,
      )
      return true
    } catch {
      setCopiedText(null)
      return false
    }
  }

  return [copiedText, copy]
}
