import type { Metadata } from "next";
import "./system.css";

export const metadata: Metadata = {
  title: "IDA Financial Data Control Tower",
  description:
    "An independent financial-data assurance prototype using public World Bank IDA data.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
