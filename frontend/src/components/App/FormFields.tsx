import { Eye, EyeOff } from "lucide-react"
import { type ComponentProps, type ReactNode, useState } from "react"
import {
  type Control,
  Controller,
  type FieldPath,
  type FieldValues,
} from "react-hook-form"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Field,
  FieldContent,
  FieldDescription,
  FieldError,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group"
import { Spinner } from "@/components/ui/spinner"

// shadcn's react-hook-form recipe: Controller + Field + FieldLabel + FieldError.

interface FieldProps<T extends FieldValues> {
  control: Control<T>
  name: FieldPath<T>
  label: ReactNode
  description?: ReactNode
  labelEnd?: ReactNode
  className?: string
}

export function TextField<T extends FieldValues>({
  control,
  name,
  label,
  description,
  labelEnd,
  className,
  ...input
}: FieldProps<T> & Omit<ComponentProps<typeof Input>, "name">) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <Field data-invalid={fieldState.invalid} className={className}>
          <div className="flex items-center">
            <FieldLabel htmlFor={name}>{label}</FieldLabel>
            {labelEnd && <span className="ml-auto">{labelEnd}</span>}
          </div>
          <Input
            {...input}
            {...field}
            value={field.value ?? ""}
            id={name}
            aria-invalid={fieldState.invalid}
          />
          {description && <FieldDescription>{description}</FieldDescription>}
          {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
        </Field>
      )}
    />
  )
}

export function PasswordField<T extends FieldValues>({
  control,
  name,
  label,
  description,
  labelEnd,
  className,
  ...input
}: FieldProps<T> &
  Omit<ComponentProps<typeof InputGroupInput>, "name" | "type">) {
  const [visible, setVisible] = useState(false)
  return (
    <Controller
      control={control}
      name={name}
      render={({ field, fieldState }) => (
        <Field data-invalid={fieldState.invalid} className={className}>
          <div className="flex items-center">
            <FieldLabel htmlFor={name}>{label}</FieldLabel>
            {labelEnd && <span className="ml-auto">{labelEnd}</span>}
          </div>
          <InputGroup>
            <InputGroupInput
              {...input}
              {...field}
              value={field.value ?? ""}
              id={name}
              type={visible ? "text" : "password"}
              aria-invalid={fieldState.invalid}
            />
            <InputGroupAddon align="inline-end">
              <InputGroupButton
                size="icon-xs"
                aria-label={
                  visible
                    ? "Masquer le mot de passe"
                    : "Afficher le mot de passe"
                }
                onClick={() => setVisible((value) => !value)}
              >
                {visible ? <EyeOff /> : <Eye />}
              </InputGroupButton>
            </InputGroupAddon>
          </InputGroup>
          {description && <FieldDescription>{description}</FieldDescription>}
          {fieldState.invalid && <FieldError errors={[fieldState.error]} />}
        </Field>
      )}
    />
  )
}

export function CheckboxField<T extends FieldValues>({
  control,
  name,
  label,
  description,
}: Omit<FieldProps<T>, "labelEnd" | "className">) {
  return (
    <Controller
      control={control}
      name={name}
      render={({ field }) => (
        <Field orientation="horizontal">
          <Checkbox
            id={name}
            checked={!!field.value}
            onCheckedChange={(checked) => field.onChange(checked === true)}
          />
          <FieldContent>
            <FieldLabel htmlFor={name}>{label}</FieldLabel>
            {description && <FieldDescription>{description}</FieldDescription>}
          </FieldContent>
        </Field>
      )}
    />
  )
}

export function SubmitButton({
  pending,
  children,
  ...props
}: { pending: boolean } & ComponentProps<typeof Button>) {
  return (
    <Button type="submit" disabled={pending} {...props}>
      {pending && <Spinner data-icon="inline-start" />}
      {children}
    </Button>
  )
}
