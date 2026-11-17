import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import DeleteConfirmation from "./DeleteConfirmation"

const DeleteAccount = () => (
  <Card>
    <CardHeader>
      <CardTitle>Supprimer mon compte</CardTitle>
      <CardDescription>
        Supprime définitivement votre compte et tous ses documents.
      </CardDescription>
    </CardHeader>
    <CardFooter>
      <DeleteConfirmation />
    </CardFooter>
  </Card>
)

export default DeleteAccount
