import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Trợ lý Khai báo Thuế",
  description: "Dành cho Hộ Kinh doanh Nhỏ - Tư duy Trí tuệ Nhân tạo",
  icons: {
    icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path fill="%232563eb" d="M320 0c17.7 0 32 14.3 32 32V96H472c22.1 0 40 17.9 40 40V352c0 22.1-17.9 40-40 40H384v56c0 35.3-28.7 64-64 64H192c-35.3 0-64-28.7-64-64V392H40c-22.1 0-40-17.9-40-40V136c0-22.1 17.9-40 40-40H160V32c0-17.7 14.3-32 32-32h128zM192 160c-17.7 0-32 14.3-32 32v64c0 17.7 14.3 32 32 32h128c17.7 0 32-14.3 32-32V192c0-17.7-14.3-32-32-32H192zm-48 160H80v48h64v-48zm224 0v48h64v-48h-64z"/></svg>'
  }
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi">
      <head>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
      </head>
      <body>{children}</body>
    </html>
  );
}
