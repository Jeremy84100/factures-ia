import { DocumentsService } from "@/client"

// The tab is opened right away, during the tap: phones block windows opened
// later, once the file has been downloaded.
export async function openPdf(id: string) {
  const tab = window.open("", "_blank")
  try {
    const { data } = await DocumentsService.readDocumentFile({
      path: { id },
      responseType: "blob",
    })
    const url = URL.createObjectURL(data as Blob)
    if (tab) tab.location.href = url
    else window.location.href = url
  } catch (error) {
    tab?.close()
    throw error
  }
}
