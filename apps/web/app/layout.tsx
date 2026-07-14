import type { ReactNode } from "react"
import "./globals.css"

export const metadata = {
  title: "Work Discovery AI",
  description: "M1/M2 clickable interview flow",
}

export default function RootLayout({ children }: { readonly children: ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  )
}
