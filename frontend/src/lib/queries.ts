import { queryOptions, useQueryClient } from "@tanstack/react-query"

import {
  type DocumentsPublic,
  DocumentsService,
  ReconciliationsService,
  SuppliersService,
  UsersService,
} from "@/client"
import { isBusy } from "@/lib/documents"

export const DEMO_DOMAIN = "@demo.example.com"
const POLL_MS = 2000

export const currentUserQuery = queryOptions({
  queryKey: ["currentUser"],
  queryFn: async () => (await UsersService.readUserMe()).data,
  staleTime: 5 * 60_000,
})

// Every document at once (500 max): tabs filter in the browser, instantly.
export const documentsQuery = queryOptions({
  queryKey: ["documents", "all"],
  queryFn: async () =>
    (await DocumentsService.readDocuments({ query: { skip: 0, limit: 500 } }))
      .data,
})

export const purchasesQuery = queryOptions({
  queryKey: ["purchases"],
  queryFn: async () => (await ReconciliationsService.readPurchases()).data,
})

export const suppliersQuery = queryOptions({
  queryKey: ["suppliers"],
  queryFn: async () => (await SuppliersService.readSuppliers()).data,
})

export const supplierQuery = (id: string) =>
  queryOptions({
    queryKey: ["suppliers", id],
    queryFn: async () =>
      (await SuppliersService.readSupplier({ path: { id } })).data,
  })

const reading = (data: DocumentsPublic | undefined) =>
  data?.data.some(isBusy) ?? false

// While the AI reads, documents and purchases refresh every 2 seconds.
export function useLiveOptions() {
  const queryClient = useQueryClient()
  const busy = () =>
    reading(queryClient.getQueryData(documentsQuery.queryKey)) ? POLL_MS : false
  return {
    documents: { ...documentsQuery, refetchInterval: busy },
    purchases: { ...purchasesQuery, refetchInterval: busy },
  }
}
