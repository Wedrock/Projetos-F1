import type { Metadata, Viewport } from "next";
import "./globals.css";
import AuthGate from "@/components/AuthGate";
import { PaywallOverlay } from "@/components/PaywallNotice";

export const metadata: Metadata = {
  title: "Box Box",
  description: "Replay e telemetria de corridas de Fórmula 1",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [{ url: "/favicon.svg", type: "image/svg+xml" }],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180" }],
  },
  // Added to the iPhone's Home Screen it opens full screen, like an app
  appleWebApp: {
    capable: true,
    title: "Box Box",
    statusBarStyle: "black-translucent",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#15151E",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body className="bg-f1-dark text-f1-text antialiased">
        <AuthGate>
          {children}
          <PaywallOverlay />
        </AuthGate>
      </body>
    </html>
  );
}
