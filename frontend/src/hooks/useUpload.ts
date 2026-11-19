import { useMutation, useQueryClient } from "@tanstack/react-query"

import { type DocumentPublic, DocumentsService } from "@/client"
import useCustomToast from "@/hooks/useCustomToast"
import { isBusy, needsReview } from "@/lib/documents"
import { handleError } from "@/utils"

export const ACCEPTED = "application/pdf,image/jpeg,image/png,image/webp"
const MAX_BATCH_BYTES = 3_500_000 // Vercel refuses requests above 4.5 MB
const MAX_BATCH_FILES = 20
const MAX_SIDE = 2000

const isPhoto = (file: File) => file.type.startsWith("image/")

// A 5 MB phone photo becomes ~400 KB: faster on 4G, and under Vercel's limit.
async function shrink(file: File): Promise<File> {
  if (!isPhoto(file) || file.size < 600_000) return file
  try {
    const bitmap = await createImageBitmap(file, {
      imageOrientation: "from-image",
    })
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height))
    const canvas = document.createElement("canvas")
    canvas.width = Math.round(bitmap.width * scale)
    canvas.height = Math.round(bitmap.height * scale)
    canvas
      .getContext("2d")
      ?.drawImage(bitmap, 0, 0, canvas.width, canvas.height)
    bitmap.close()
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", 0.85),
    )
    if (!blob) return file
    const name = file.name.replace(/\.[^.]+$/, "") || "photo"
    return new File([blob], `${name}.jpg`, { type: "image/jpeg" })
  } catch {
    return file
  }
}

function batches(files: File[]): File[][] {
  const result: File[][] = []
  let current: File[] = []
  let size = 0
  for (const file of files) {
    const full =
      current.length >= MAX_BATCH_FILES || size + file.size > MAX_BATCH_BYTES
    if (current.length > 0 && full) {
      result.push(current)
      current = []
      size = 0
    }
    current.push(file)
    size += file.size
  }
  if (current.length > 0) result.push(current)
  return result
}

export function useUpload() {
  const queryClient = useQueryClient()
  const { showSuccessToast, showErrorToast } = useCustomToast()

  const mutation = useMutation({
    mutationFn: async (files: File[]) => {
      const ready = await Promise.all(files.map(shrink))
      const uploaded: DocumentPublic[] = []
      for (const batch of batches(ready)) {
        const { data } = await DocumentsService.uploadDocuments({
          body: { files: batch },
        })
        uploaded.push(...data.data)
        await queryClient.invalidateQueries({ queryKey: ["documents"] })
        await queryClient.invalidateQueries({ queryKey: ["purchases"] })
      }
      return uploaded
    },
    onSuccess: (uploaded) => {
      const count = uploaded.length
      if (uploaded.some(isBusy)) {
        showSuccessToast(
          count > 1
            ? `${count} documents reçus, l'IA les lit`
            : "Document reçu, l'IA le lit",
        )
        return
      }
      const toReview = uploaded.filter(needsReview).length
      if (count === 1) {
        showSuccessToast(
          toReview > 0 ? "Document lu, à vérifier" : "Document lu",
        )
        return
      }
      showSuccessToast(
        toReview > 0
          ? `${count} documents lus (${toReview} à vérifier)`
          : `${count} documents lus`,
      )
    },
    onError: handleError.bind(showErrorToast),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] })
      queryClient.invalidateQueries({ queryKey: ["purchases"] })
      queryClient.invalidateQueries({ queryKey: ["suppliers"] })
    },
  })

  return {
    upload: (files: File[]) => {
      if (files.length > 0) mutation.mutate(files)
    },
    isPending: mutation.isPending,
  }
}
