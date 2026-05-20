/**
 * Generează og-image.png (1200×630) pentru preview-ul de link Open Graph.
 * Rulare: node scripts/gen-og-image.mjs
 */
import sharp from 'sharp';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { writeFileSync } from 'fs';

const __dir = dirname(fileURLToPath(import.meta.url));
const outPath = join(__dir, '../public/og-image.png');

const W = 1200, H = 630;

// SVG-ul imaginii de preview — design inspirat din CMYK printing
const svg = `
<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <!-- Background gradient albastru închis -->
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"   stop-color="#0f1f3d"/>
      <stop offset="100%" stop-color="#1a3560"/>
    </linearGradient>
    <!-- Halftone dots subtile -->
    <pattern id="dots" width="40" height="40" patternUnits="userSpaceOnUse">
      <circle cx="20" cy="20" r="1.5" fill="white" opacity="0.04"/>
    </pattern>
  </defs>

  <rect width="${W}" height="${H}" fill="url(#bg)"/>
  <rect width="${W}" height="${H}" fill="url(#dots)"/>

  <!-- Linie decorativă sus -->
  <rect x="0" y="0" width="${W}" height="6" fill="#00AEEF" opacity="0.7"/>

  <!-- Bloc CMYK pătrate (stânga) -->
  <rect x="72"  y="200" width="110" height="110" rx="14" fill="#00AEEF"/>
  <rect x="197" y="200" width="110" height="110" rx="14" fill="#EC008C"/>
  <rect x="72"  y="325" width="110" height="110" rx="14" fill="#FCD200"/>
  <rect x="197" y="325" width="110" height="110" rx="14" fill="#F0F0F0" opacity="0.15"/>
  <!-- "K" în pătratul negru -->
  <text x="252" y="400" font-family="Georgia, serif" font-size="54" font-weight="bold"
        fill="#F0F0F0" opacity="0.6" text-anchor="middle">K</text>

  <!-- Separator vertical -->
  <rect x="355" y="180" width="2" height="270" fill="white" opacity="0.12"/>

  <!-- Text principal -->
  <text x="410" y="290"
        font-family="'Helvetica Neue', Helvetica, Arial, sans-serif"
        font-size="80" font-weight="700" fill="white" letter-spacing="-1">
    ARTA GRAFICA
  </text>
  <text x="412" y="360"
        font-family="'Helvetica Neue', Helvetica, Arial, sans-serif"
        font-size="34" font-weight="400" fill="#93c5fd" letter-spacing="3">
    PLANIFICARE PRODUCȚIE
  </text>

  <!-- Subtitlu mic -->
  <text x="412" y="430"
        font-family="'Helvetica Neue', Helvetica, Arial, sans-serif"
        font-size="22" fill="#60a5fa" opacity="0.75">
    Gestionare comenzi · Gantt · Asistent AI
  </text>

  <!-- Linie decorativă jos -->
  <rect x="0" y="${H - 6}" width="${W}" height="6">
    <linearGradient id="lb" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"   stop-color="#00AEEF"/>
      <stop offset="33%"  stop-color="#EC008C"/>
      <stop offset="66%"  stop-color="#FCD200"/>
      <stop offset="100%" stop-color="#333333"/>
    </linearGradient>
    <rect x="0" y="${H - 6}" width="${W}" height="6" fill="url(#lb)"/>
  </rect>
  <rect x="0" y="${H - 6}" width="${W}" height="6" fill="none"/>
  <!-- gradient CMYK pe bara de jos -->
  <rect x="0"   y="${H - 6}" width="300" height="6" fill="#00AEEF" opacity="0.85"/>
  <rect x="300" y="${H - 6}" width="300" height="6" fill="#EC008C" opacity="0.85"/>
  <rect x="600" y="${H - 6}" width="300" height="6" fill="#FCD200" opacity="0.85"/>
  <rect x="900" y="${H - 6}" width="300" height="6" fill="#E0E0E0" opacity="0.20"/>
</svg>
`.trim();

await sharp(Buffer.from(svg))
  .png()
  .toFile(outPath);

console.log(`✅  og-image.png generat: ${outPath}`);
