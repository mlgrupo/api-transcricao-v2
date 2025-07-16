import type { Metadata } from "next";
import "./globals.css";
import Logo from "./components/Logo";

export const metadata: Metadata = {
  title: "Reconecta Transcript",
  description: "Sistema automatizado de transcrição de áudio/vídeo",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body style={{ 
        background: '#111111',
        color: '#FFE1A6',
        fontFamily: 'Inter, sans-serif',
        minHeight: '100vh',
        margin: 0,
        padding: 0
      }}>
        <main className="main" style={{
          minHeight: '100vh',
          background: '#111111',
          padding: '2rem 0'
        }}>
          <div className="container" style={{
            maxWidth: '1200px',
            margin: '0 auto',
            padding: '0 20px',
            background: 'transparent'
          }}>
            
            {children}
          </div>
        </main>
      </body>
    </html>
  );
}
