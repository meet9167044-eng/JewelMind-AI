import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'JewelMind — Business Intelligence for Jewellers',
  description: 'Explainable analytics, profit diagnosis, inventory intelligence, and metal exposure tracking — built for retail jewellers.',
  keywords: 'jewellery, analytics, BI, profit, inventory, metal, gold, silver',
  openGraph: {
    title: 'JewelMind',
    description: 'Your jewellery business, fully understood.',
    type: 'website',
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>{children}</body>
    </html>
  )
}
