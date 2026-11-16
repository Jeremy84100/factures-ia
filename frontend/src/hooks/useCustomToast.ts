import { toast } from "sonner"

const useCustomToast = () => {
  const showSuccessToast = (description: string) => {
    toast.success("C'est fait", {
      description,
    })
  }

  const showErrorToast = (description: string) => {
    toast.error("Une erreur est survenue", {
      description,
    })
  }

  return { showSuccessToast, showErrorToast }
}

export default useCustomToast
