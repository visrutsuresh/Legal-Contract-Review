import type { Metadata } from "next";
import { array, cabinet, gsans } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nimbus Support",
  description: "Support desk powered by Enklima",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${gsans.variable} ${cabinet.variable} ${array.variable} h-full antialiased`}
    >
      <body suppressHydrationWarning className="min-h-full flex flex-col">
        {children}
      </body>
    </html>
  );
}
