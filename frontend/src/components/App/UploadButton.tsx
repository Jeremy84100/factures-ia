import { Loader2, Plus } from "lucide-react"
import { type ReactNode, useRef } from "react"

import { Button } from "@/components/ui/button"
import { ACCEPTED, useUpload } from "@/hooks/useUpload"
import { cn } from "@/lib/utils"

export function useFilePicker() {
  const input = useRef<HTMLInputElement>(null)
  const { upload, isPending } = useUpload()
  const picker = (
    <input
      ref={input}
      type="file"
      accept={ACCEPTED}
      multiple
      hidden
      data-testid="document-input"
      onChange={(e) => {
        upload(Array.from(e.target.files ?? []))
        e.target.value = ""
      }}
    />
  )
  return { picker, open: () => input.current?.click(), upload, isPending }
}

export function UploadButton({
  className,
  children = "Ajouter des documents",
}: {
  className?: string
  children?: ReactNode
}) {
  const { picker, open, isPending } = useFilePicker()
  return (
    <>
      {picker}
      <Button
        onClick={open}
        disabled={isPending}
        className={cn("h-11 rounded-full px-5", className)}
      >
        {isPending ? <Loader2 className="animate-spin" /> : <Plus />}
        {isPending ? "Envoi…" : children}
      </Button>
    </>
  )
}

// The round "+" in the middle of the phone's bottom bar.
export function UploadFab() {
  const { picker, open, isPending } = useFilePicker()
  return (
    <>
      {picker}
      <button
        type="button"
        onClick={open}
        disabled={isPending}
        aria-label="Ajouter des documents"
        className="-mt-5 flex size-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/30 transition-transform active:scale-95"
      >
        {isPending ? (
          <Loader2 className="size-6 animate-spin" />
        ) : (
          <Plus className="size-7" />
        )}
      </button>
    </>
  )
}
