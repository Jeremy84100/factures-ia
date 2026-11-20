// Apply the saved theme before the first paint: no white flash in dark mode.
;(() => {
  let theme = "system"
  try {
    theme = localStorage.getItem("vite-ui-theme") || "system"
  } catch {}
  const dark =
    theme === "dark" ||
    (theme === "system" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches)
  document.documentElement.classList.add(dark ? "dark" : "light")
  document.documentElement.style.colorScheme = dark ? "dark" : "light"
})()
