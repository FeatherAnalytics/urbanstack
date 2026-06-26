import type { Metadata } from "next";
import { Geist, Geist_Mono, DM_Serif_Display } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const dmSerif = DM_Serif_Display({
  weight: "400",
  variable: "--font-display",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "UrbanStack — Urban Data Explorer",
  description:
    "Compare demographics, transit, safety, spending, and congestion across U.S. metro areas with interactive choropleth maps and bivariate analysis.",
  authors: [{ name: "David Hardage", url: "https://featheranalytics.dev" }],
  openGraph: {
    title: "UrbanStack — Urban Data Explorer",
    description:
      "Compare demographics, transit, safety, spending, and congestion across U.S. metro areas with interactive choropleth maps and bivariate analysis.",
    url: "https://featheranalytics.dev/urbanstack/",
    siteName: "UrbanStack",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "UrbanStack — Urban Data Explorer",
    description:
      "Interactive choropleth maps comparing demographics, transit, safety, and congestion across U.S. metros.",
  },
  other: {
    "linkedin:owner": "https://www.linkedin.com/in/david-hardage/",
  },
};

/**
 * Inline script that runs before paint to set the dark class on <html>.
 * Reads localStorage first; falls back to system preference.
 * Prevents flash of wrong theme on load.
 */
const themeScript = `
(function(){
  try {
    var stored = localStorage.getItem('urbanstack-theme');
    if (stored === 'dark' || (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  } catch(e){}
})();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${dmSerif.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
