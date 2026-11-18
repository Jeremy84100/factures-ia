import { createFileRoute } from "@tanstack/react-router"

import ChangePassword from "@/components/UserSettings/ChangePassword"
import MyData from "@/components/UserSettings/MyData"
import UserInformation from "@/components/UserSettings/UserInformation"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import useAuth from "@/hooks/useAuth"
import { documentsQuery } from "@/lib/queries"

const TABS = [
  { value: "profile", title: "Profil", component: UserInformation },
  { value: "password", title: "Mot de passe", component: ChangePassword },
  { value: "data", title: "Mes données", component: MyData },
]

export const Route = createFileRoute("/_layout/settings")({
  loader: ({ context }) => context.queryClient.ensureQueryData(documentsQuery),
  component: UserSettings,
  head: () => ({ meta: [{ title: "Mon compte - Factures IA" }] }),
})

// The page title "Mon compte" is in the header: no second title here.
function UserSettings() {
  const { user } = useAuth()
  if (!user) return null
  return (
    <Tabs defaultValue="profile">
      <TabsList>
        {TABS.map((tab) => (
          <TabsTrigger key={tab.value} value={tab.value}>
            {tab.title}
          </TabsTrigger>
        ))}
      </TabsList>
      {TABS.map((tab) => (
        <TabsContent key={tab.value} value={tab.value}>
          <tab.component />
        </TabsContent>
      ))}
    </Tabs>
  )
}
