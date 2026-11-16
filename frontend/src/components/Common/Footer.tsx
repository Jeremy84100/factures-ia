export function Footer() {
  const currentYear = new Date().getFullYear()

  return (
    <footer className="border-t py-4 px-6">
      <p className="text-center text-muted-foreground text-sm sm:text-left">
        Factures IA - {currentYear} · basé sur{" "}
        <a
          href="https://github.com/fastapi/full-stack-fastapi-template"
          target="_blank"
          rel="noopener noreferrer"
          className="underline underline-offset-4 hover:text-foreground"
        >
          Full Stack FastAPI Template
        </a>
      </p>
    </footer>
  )
}
