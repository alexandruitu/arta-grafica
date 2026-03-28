/**
 * Generates Ghid_Utilizare_Arta_Grafica.docx
 * Run: node create_guide_docx.js
 */
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak, LevelFormat,
} = require("docx");
const fs = require("fs");

// ── Page geometry ────────────────────────────────────────────────────────────
// A4: 11906 × 16838 DXA;  2 cm margin = 1134 DXA each side
const PAGE_W   = 11906;
const PAGE_H   = 16838;
const MARGIN   = 1134;           // 2 cm
const CONTENT  = PAGE_W - 2 * MARGIN;  // 9638 DXA

// ── Colours ──────────────────────────────────────────────────────────────────
const C_BLUE    = "3b82f6";
const C_DARK    = "1e293b";
const C_SLATE   = "475569";
const C_BG      = "f1f5f9";
const C_WHITE   = "FFFFFF";
const C_GREEN   = "16a34a";
const C_RED     = "dc2626";
const C_AMBER   = "d97706";
const C_ORANGE  = "ea580c";

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Plain body paragraph */
function body(text, opts = {}) {
  const runs = [];
  // Support very basic inline bold: **text**
  let remaining = text;
  const re = /\*\*(.+?)\*\*/g;
  let m, last = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) runs.push(new TextRun({ text: text.slice(last, m.index), ...opts.run }));
    runs.push(new TextRun({ text: m[1], bold: true, ...opts.run }));
    last = m.index + m[0].length;
  }
  if (last < text.length) runs.push(new TextRun({ text: text.slice(last), ...opts.run }));
  return new Paragraph({
    children: runs.length ? runs : [new TextRun({ text, ...opts.run })],
    spacing: { after: 120 },
    alignment: AlignmentType.JUSTIFIED,
    ...opts.para,
  });
}

/** Bullet item */
function bullet(text, ref = "bullets") {
  const runs = [];
  const re = /\*\*(.+?)\*\*/g;
  let m, last = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) runs.push(new TextRun({ text: text.slice(last, m.index) }));
    runs.push(new TextRun({ text: m[1], bold: true }));
    last = m.index + m[0].length;
  }
  if (last < text.length) runs.push(new TextRun({ text: text.slice(last) }));
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    children: runs.length ? runs : [new TextRun({ text })],
    spacing: { after: 80 },
  });
}

/** Note / callout box */
function note(text) {
  return new Paragraph({
    children: [new TextRun({ text, italics: true, color: C_SLATE, size: 20 })],
    spacing: { before: 80, after: 160 },
    indent: { left: 400 },
    border: {
      left: { style: BorderStyle.SINGLE, size: 12, color: C_BLUE, space: 10 },
    },
  });
}

/** Spacer paragraph */
function spacer(pts = 100) {
  return new Paragraph({ children: [], spacing: { after: pts } });
}

// ── Table builder ─────────────────────────────────────────────────────────────

const CELL_BORDER = {
  top:    { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1" },
  bottom: { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1" },
  left:   { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1" },
  right:  { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1" },
};

function cell(text, {
  bg = C_WHITE, bold = false, color = C_DARK, fontSize = 20,
  w, colIdx, isHeader = false,
} = {}) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    borders: CELL_BORDER,
    shading: { fill: bg, type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 100, right: 100 },
    verticalAlign: VerticalAlign.TOP,
    children: [new Paragraph({
      children: [new TextRun({ text: String(text), bold: bold || isHeader, color, size: fontSize })],
      spacing: { after: 0 },
    })],
  });
}

/** Scale PDF colWidths (summing to pdfSum) → DXA (summing to CONTENT) */
function scaleCols(pdfCols) {
  const pdfSum = pdfCols.reduce((a, b) => a + b, 0);
  const dxa = pdfCols.map(c => Math.round((c / pdfSum) * CONTENT));
  // Fix rounding error on last column
  const diff = CONTENT - dxa.reduce((a, b) => a + b, 0);
  dxa[dxa.length - 1] += diff;
  return dxa;
}

/**
 * Build a simple table.
 * @param {string[][]} rows  - first row = header
 * @param {number[]} pdfCols - original PDF colWidths
 * @param {object}  opts
 */
function makeTable(rows, pdfCols, { headerBg = C_DARK, altBg = C_BG, fontSize = 20 } = {}) {
  const cols = scaleCols(pdfCols);

  return new Table({
    width: { size: CONTENT, type: WidthType.DXA },
    columnWidths: cols,
    rows: rows.map((row, ri) => {
      const isHeader = ri === 0;
      const bg = isHeader ? headerBg : (ri % 2 === 0 ? C_WHITE : altBg);
      return new TableRow({
        tableHeader: isHeader,
        children: row.map((text, ci) => {
          // Support colour markers like [RED], [GREEN], [AMBER], [ORANGE], [SLATE]
          let color = isHeader ? C_WHITE : C_DARK;
          let bold = isHeader;
          let cleanText = String(text);
          const colorMatch = cleanText.match(/^\[([A-Z]+)\]\s*/);
          if (colorMatch) {
            const map = { RED: C_RED, GREEN: C_GREEN, AMBER: C_AMBER, ORANGE: C_ORANGE, SLATE: C_SLATE };
            color = map[colorMatch[1]] || color;
            bold = true;
            cleanText = cleanText.slice(colorMatch[0].length);
          }
          return new TableCell({
            width: { size: cols[ci], type: WidthType.DXA },
            borders: CELL_BORDER,
            shading: { fill: bg, type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 100, right: 100 },
            verticalAlign: VerticalAlign.TOP,
            children: [new Paragraph({
              children: [new TextRun({ text: cleanText, bold, color, size: fontSize })],
              spacing: { after: 0 },
            })],
          });
        }),
      });
    }),
  });
}

// ── Document assembly ─────────────────────────────────────────────────────────

const numbering = {
  config: [
    {
      reference: "bullets",
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: "\u2022",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 600, hanging: 300 } } },
      }],
    },
  ],
};

const styles = {
  default: {
    document: { run: { font: "Arial", size: 22, color: C_DARK } },
  },
  paragraphStyles: [
    {
      id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { size: 36, bold: true, font: "Arial", color: C_BLUE },
      paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 },
    },
    {
      id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { size: 28, bold: true, font: "Arial", color: C_DARK },
      paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 1 },
    },
    {
      id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { size: 24, bold: true, font: "Arial", color: C_SLATE },
      paragraph: { spacing: { before: 180, after: 120 }, outlineLevel: 2 },
    },
  ],
};

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text, bold: true, size: 36, color: C_BLUE, font: "Arial" })], spacing: { before: 360, after: 200 } });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text, bold: true, size: 28, color: C_DARK, font: "Arial" })], spacing: { before: 240, after: 160 } });
}
function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text, bold: true, size: 24, color: C_SLATE, font: "Arial" })], spacing: { before: 180, after: 120 } });
}

// ─────────────────────────────────────────────────────────────────────────────
//  C O N T E N T
// ─────────────────────────────────────────────────────────────────────────────

const children = [];

// ── Cover page ────────────────────────────────────────────────────────────────
children.push(spacer(2000));
children.push(new Paragraph({
  children: [new TextRun({ text: "Arta Grafica", bold: true, size: 72, color: C_DARK, font: "Arial" })],
  alignment: AlignmentType.CENTER,
  spacing: { after: 100 },
}));
children.push(new Paragraph({
  children: [new TextRun({ text: "Planificare Productie", size: 48, color: C_SLATE, font: "Arial" })],
  alignment: AlignmentType.CENTER,
  spacing: { after: 400 },
}));
children.push(new Paragraph({
  children: [new TextRun({ text: "Ghid de Utilizare", bold: true, size: 40, color: C_DARK, font: "Arial" })],
  alignment: AlignmentType.CENTER,
  spacing: { after: 200 },
}));
children.push(new Paragraph({
  children: [new TextRun({ text: "Versiunea 1.0 \u2013 Martie 2026", size: 24, color: C_SLATE, font: "Arial" })],
  alignment: AlignmentType.CENTER,
  spacing: { after: 0 },
}));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ── Table of contents ─────────────────────────────────────────────────────────
children.push(h1("Cuprins"));
children.push(makeTable([
  ["Nr.", "Sectiune", "Descriere"],
  ["1.", "Dashboard", "Prezentare generala si actiuni principale"],
  ["2.", "Gantt", "Vizualizare temporala a planificarii"],
  ["3.", "Board Masini", "Vizualizare pe resurse (masini)"],
  ["4.", "Comenzi", "Lista comenzilor de productie"],
  ["5.", "Planificare", "Rezultatele algoritmului de planificare"],
  ["6.", "Stoc Materiale", "Situatia stocurilor si deficitelor"],
  ["7.", "Algoritmul de Planificare", "Descriere detaliata a logicii"],
], [25, 100, 310], { headerBg: C_BLUE }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 1. Dashboard ──────────────────────────────────────────────────────────────
children.push(h1("1. Dashboard"));
children.push(body("Dashboard-ul este ecranul principal al aplicatiei. Ofera o privire de ansamblu asupra intregii activitati de productie si permite executarea actiunilor principale."));

children.push(h2("Actiuni disponibile"));
children.push(bullet("**Import Date Excel** \u2013 Incarca datele din fisierele Excel exportate din ERP (comenzi, operatii dispatch, operatii catalog, deficit/stoc, resurse si program resurse). Aceasta este prima actiune necesara dupa o actualizare a datelor din ERP."));
children.push(bullet("**Ruleaza Planificarea** \u2013 Executa algoritmul de planificare automata. Analizeaza toate comenzile active si aloca operatiile pe resurse in functie de disponibilitate, materiale, BT si dependente de rank. Rezultatele sunt vizibile in tab-urile Gantt, Board Masini si Planificare."));

children.push(spacer(160));
children.push(h2("Carduri statistice"));
children.push(makeTable([
  ["Card", "Descriere"],
  ["Total Comenzi", "Numarul total de comenzi incarcate in sistem (inclusiv STOP)"],
  ["Comenzi Active", "Comenzi cu status LIBER (pot fi planificate)"],
  ["Comenzi STOP", "Comenzi blocate/suspendate (excluse din planificare)"],
  ["Operatii Dispatch", "Total operatii din listele de dispatch (munca de executat)"],
  ["Resurse", "Numarul de masini/oameni disponibili pentru planificare"],
], [120, 345], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(body("Sub carduri se afiseaza graficele Stadiu Prepress (distributia comenzilor pe stadii) si informatii despre ultima sesiune de planificare executata."));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 2. Gantt ──────────────────────────────────────────────────────────────────
children.push(h1("2. Gantt"));
children.push(body("Tab-ul Gantt afiseaza o diagrama de tip Gantt cu toate operatiile planificate. Fiecare bara reprezinta o operatie alocata pe o resursa, cu durata si dependentele vizibile."));

children.push(h2("Functionalitati"));
children.push(bullet("**Filtru Centru de Lucru** \u2013 Selecteaza un centru de lucru (CL) pentru a vedea doar operatiile aferente (ex: FAL, SM, BINDER)"));
children.push(bullet("**Cautare WO** \u2013 Cauta o comanda specifica dupa numarul WO"));
children.push(bullet("**Vizualizare Day/Week/Month** \u2013 Schimba granularitatea axei temporale"));
children.push(bullet("**Buton Today** \u2013 Navigheaza rapid la data curenta"));

children.push(h2("Navigare"));
children.push(bullet("**Scroll vertical** \u2013 Deruleaza lista operatiilor"));
children.push(bullet("**Scroll orizontal** \u2013 Navigheaza in timp (stanga = trecut, dreapta = viitor)"));

children.push(spacer(160));
children.push(h2("Coduri culori"));
children.push(makeTable([
  ["Culoare", "Semnificatie"],
  ["Albastru", "Operatie planificata (in termen)"],
  ["Rosu",     "Operatie intarziata (data end depasita)"],
  ["Mov",      "Operatie blocata/frozen"],
], [120, 345], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(body("Sagetile intre bare arata dependentele (inlantuirea operatiilor). O operatie de rank superior (ex: ambalare) incepe doar dupa terminarea operatiei de rank inferior (ex: tipar)."));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 3. Board Masini ──────────────────────────────────────────────────────────
children.push(h1("3. Board Masini"));
children.push(body("Board Masini ofera o vizualizare centrata pe resurse, inspirata de solutia Theurer.com. Fiecare rand reprezinta o masina/resursa, iar pe axa orizontala se vad orele din zi. Operatiile sunt afisate ca bare colorate pozitionate in timp pe fiecare masina."));

children.push(h2("Functionalitati"));
children.push(bullet("**Filtru Centru de Lucru** \u2013 Selecteaza un CL sau vizualizeaza toate centrele simultan"));
children.push(bullet("**Buton Azi** \u2013 Navigheaza la ora curenta"));
children.push(bullet("**Bara curenta de timp** \u2013 O linie verticala rosie indica ora exacta"));

children.push(h2("Navigare"));
children.push(makeTable([
  ["Actiune", "Efect"],
  ["Scroll (rotita mouse)", "Navigheaza stanga/dreapta pe axa timpului"],
  ["Ctrl + Scroll",         "Zoom in/out (mareste/micsoreaza intervalul vizibil)"],
  ["Drag (click + trage)",  "Pan liber in orice directie"],
], [140, 325], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(h2("Informatii afisate"));
children.push(body("Badge-urile din dreapta arata: numarul de masini vizibile, numarul total de operatii planificate, si numarul de operatii intarziate (cu data de sfarsit in trecut). Tooltip-ul afisat la hover pe o bara contine detalii: WO, operatie, client, durata, interval orar."));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 4. Comenzi ───────────────────────────────────────────────────────────────
children.push(h1("4. Comenzi"));
children.push(body("Tab-ul Comenzi afiseaza lista tuturor comenzilor de productie importate din ERP. Permite cautarea si filtrarea rapida."));

children.push(h2("Carduri statistice live"));
children.push(body("In partea de sus se afiseaza 4 carduri care reflecta rezultatele cautarii/filtrarii curente:"));
children.push(makeTable([
  ["Card", "Descriere", "Actiune la click"],
  ["Total comenzi",    "Numarul total de comenzi afisate", "\u2013"],
  ["06 - In productie","Comenzi cu stadiu prepress 'In productie'", "Filtreaza dupa acest stadiu"],
  ["LIBER",            "Comenzi cu status activ", "Filtreaza dupa status LIBER"],
  ["STOP",             "Comenzi blocate", "Filtreaza dupa status STOP"],
], [100, 200, 165], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(note("Cardurile sunt interactive \u2013 un click pe un card filtreaza tabelul dupa criteriul respectiv. Al doilea click revine la vizualizarea completa. Cand se aplica un filtru sau o cautare, label-ul se schimba in \"Rezultate filtrate\"."));

children.push(h2("Cautare si filtrare"));
children.push(body("Campul de cautare permite gasirea comenzilor dupa: numar CP, numar CV, nume client, articol, sau referinta client. Dropdown-ul de status permite filtrarea dupa LIBER sau STOP."));
children.push(body("Fiecare rand din tabel poate fi expandat (click pe sageata >) pentru a vedea operatiile dispatch asociate comenzii."));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 5. Planificare ───────────────────────────────────────────────────────────
children.push(h1("5. Planificare"));
children.push(body("Tab-ul Planificare afiseaza rezultatele detaliate ale ultimei sesiuni de planificare. Fiecare operatie din dispatch apare cu statusul ei de planificare."));

children.push(h2("Carduri statistice"));
children.push(makeTable([
  ["Card", "Culoare", "Descriere"],
  ["Total afisate",  "Gri",      "Numarul de operatii vizibile dupa filtrare"],
  ["Planificate",    "Verde",    "Operatii alocate pe o resursa, cu date start/end"],
  ["Fara Material",  "Rosu",     "Operatii blocate \u2013 stoc insuficient pentru comanda"],
  ["Fara BT",        "Portocaliu","Comanda nu are Bun de Tipar valid"],
  ["Blocate Rank",   "Galben",   "Operatia asteapta finalizarea unei operatii anterioare"],
  ["Fara Resursa",   "Gri",      "Nu exista resursa disponibila in centrul de lucru"],
], [100, 70, 295], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(note("Cardurile sunt interactive \u2013 click pe un card filtreaza tabelul dupa acel status. Cardul Planificate arata si numarul total de ore planificate."));

children.push(h2("Filtre"));
children.push(bullet("**Centru de lucru** \u2013 Filtreaza dupa CL (ex: FAL, SM, BINDER, etc.)"));
children.push(bullet("**Status** \u2013 Filtreaza dupa statusul de planificare"));

children.push(spacer(160));
children.push(h2("Coloane tabel"));
children.push(makeTable([
  ["Coloana", "Descriere"],
  ["WO",         "Numarul Work Order (comanda de productie)"],
  ["OP",         "Codul operatiei din catalog"],
  ["CL",         "Centrul de lucru (tipul de masina/sectie)"],
  ["Resursa",    "Masina/persoana alocata (doar pentru Planificate)"],
  ["Status",     "Statusul operatiei (Planificat, Fara Material, etc.)"],
  ["Start / End","Datele de inceput si sfarsit planificate"],
  ["Durata (h)", "Timpul ramas de executat in ore"],
  ["Motiv",      "Motivul pentru care operatia nu a putut fi planificata"],
], [90, 375], { headerBg: C_BLUE }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 6. Stoc Materiale ────────────────────────────────────────────────────────
children.push(h1("6. Stoc Materiale"));
children.push(body("Tab-ul Stoc Materiale afiseaza situatia stocurilor de materii prime si materiale. Este esential pentru a intelege de ce anumite comenzi nu pot fi planificate."));

children.push(h2("Carduri statistice"));
children.push(makeTable([
  ["Card", "Descriere"],
  ["Total articole", "Numarul total de articole de stoc afisate"],
  ["Disponibil",     "Articole cu stoc pozitiv (sold > rezervari)"],
  ["Epuizat",        "Articole cu sold zero (fara stoc disponibil)"],
  ["Deficit",        "Articole cu disponibil negativ (cerere > stoc existent)"],
], [110, 355], { headerBg: C_BLUE }));

children.push(spacer(160));
children.push(h2("Calcul disponibil"));
children.push(body("Formula de calcul este: **Disponibil = Sold Actual + Total Rezervat**"));
children.push(body("Unde Total Rezervat este suma cantitatilor din rezervarile de tip B (comenzi de productie). Cantitatile sunt stocate cu semn negativ (consum), deci adunarea este corecta: sold + (-cantitate_rezervata) = sold - cantitate_rezervata = disponibil real."));
children.push(note("Important: Articolele cu disponibil negativ (rosu in tabel) sunt cauza directa a operatiilor marcate \"Fara Material\" in tab-ul Planificare. Aprovizionarea acestor articole va debloca planificarea comenzilor respective."));

children.push(h2("Filtrare"));
children.push(body("Cardurile Epuizat si Deficit sunt clickabile \u2013 un click filtreaza tabelul pentru a afisa doar articolele cu acel status. Campul de cautare permite gasirea rapida dupa codul articolului."));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 7. Algoritmul de Planificare ─────────────────────────────────────────────
children.push(h1("7. Algoritmul de Planificare"));
children.push(body("Algoritmul de planificare automata este componenta centrala a aplicatiei. El decide ce operatii se pot executa, pe ce masini si cand, respectand constrangerile reale de productie."));

// 7.1
children.push(h2("7.1 Ordinea de procesare a comenzilor"));
children.push(body("Comenzile sunt procesate in ordinea prioritatii. Aceasta ordine determina care comenzi primesc resurse primele:"));
children.push(makeTable([
  ["Prioritate", "Criteriu", "Exemplu"],
  ["1 (cea mai mare)", "Stadiu Prepress mai avansat", "06 - In productie > 05 - BT existent"],
  ["2",               "Data livrare mai apropiata",   "Comanda cu livrare pe 25.03 > livrare pe 30.03"],
  ["3",               "Comenzile STOP sunt excluse",  "Nu se planifica deloc"],
], [100, 170, 195], { headerBg: C_DARK }));

// 7.2
children.push(h2("7.2 Verificarile pentru fiecare operatie"));
children.push(body("Pentru fiecare comanda, operatiile sunt procesate in ordinea rank-ului (de la prima operatie \u2013 ex: tipar \u2013 la ultima \u2013 ex: ambalare). Fiecare operatie trece prin 4 verificari, in aceasta ordine:"));

children.push(h3("Verificare 1: Bun de Tipar (BT)"));
children.push(body("Se verifica daca comanda are un Bun de Tipar valid. BT-ul este documentul care autorizeaza inceperea tiparului. Daca niciun camp BT (BT1-BT4) nu este completat sau contine data invalida (1911-11-11), TOATE operatiile comenzii sunt marcate Fara BT."));

children.push(h3("Verificare 2: Dependente de Rank"));
children.push(body("Fiecare operatie are un rank (rang) care defineste ordinea de executie in cadrul unei comenzi. Exemplu: tipar (rank 1) trebuie terminat inainte de faltuit (rank 2), iar ambalarea (rank 3) vine dupa faltuit."));
children.push(makeTable([
  ["Starea operatiei precedente", "Efect asupra operatiei curente"],
  ["Completata (remaining = 0)",   "Nicio restrictie \u2013 se poate planifica imediat"],
  ["Planificata (alocata pe masina)","Se poate planifica, dar va incepe dupa data de sfarsit a operatiei precedente + 1 zi"],
  ["Deschisa (neplanificata)",     "Blocata \u2013 nu se poate planifica pana cand operatia precedenta nu este macar planificata"],
], [160, 305], { headerBg: C_DARK }));

children.push(spacer(120));
children.push(note("Cand o comanda are mai multe operatii la acelasi rank (ex: doua operatii rank 2 pe centre de lucru diferite), algoritmul pastreaza cel mai restrictiv status. Daca cel putin o operatie la rank 2 este 'deschisa', toate operatiile de rank 3+ sunt blocate. Daca cel putin una este 'planificata', rank 3+ asteapta cea mai tarzie data de sfarsit dintre toate operatiile de rank 2."));

children.push(h3("Verificare 3: Disponibilitate Materiale"));
children.push(body("Se verifica daca materialele necesare comenzii sunt disponibile in stoc. Verificarea se face la nivel de comanda (WO), nu la nivel de operatie."));
children.push(body("Algoritmul simuleaza un consum secvential: pe masura ce comenzile cu prioritate mai mare sunt planificate, ele 'consuma' din stocul disponibil. Comenzile cu prioritate mai mica pot gasi stocul epuizat chiar daca la nivel global pare suficient. Acestea sunt marcate Fara Material."));

children.push(h3("Verificare 4: Alocare pe Resursa"));
children.push(body("Daca toate verificarile anterioare sunt trecute, algoritmul cauta o resursa (masina/om) disponibila in centrul de lucru corespunzator operatiei."));
children.push(body("Se cauta prima resursa care are ore disponibile incepand de la **earliest_start** (data cea mai devreme permisa de dependentele de rank sau data de azi). Operatia poate fi distribuita pe mai multe zile daca nu incape intr-o singura zi."));

children.push(spacer(160));
children.push(makeTable([
  ["Pas", "Actiune"],
  ["1", "Se calculeaza durata ramasa: P_Setup + P_Runtime - R_Runtime"],
  ["2", "Se cauta resurse din CL-ul operatiei care suporta codul operatiei"],
  ["3", "Pentru fiecare resursa, se cauta prima zi cu ore disponibile >= earliest_start"],
  ["4", "Se aloca orele: daca ziua are suficient, se aloca totul; daca nu, se aloca partial si se continua pe ziua urmatoare"],
  ["5", "Se scad orele alocate din capacitatea resursei (nu se mai pot folosi de alte operatii)"],
], [30, 435], { headerBg: C_DARK }));

// 7.3
children.push(h2("7.3 Schema decizionala"));
children.push(body("Diagrama de mai jos rezuma fluxul de decizie pentru fiecare operatie:"));
children.push(makeTable([
  ["", "Decizie / Actiune", "Rezultat"],
  ["1", "Operatia este deja terminata? (remaining = 0)",          "[GREEN] DA: Skip (completata)"],
  ["2", "Comanda are BT valid?",                                   "[ORANGE] NU: Status = Fara BT"],
  ["3", "Toate operatiile de rank inferior sunt completate sau planificate?", "[AMBER] NU: Status = Blocat Rank"],
  ["4", "Materialele comenzii sunt disponibile in stoc?",          "[RED] NU: Status = Fara Material"],
  ["5", "Exista resursa disponibila in CL-ul operatiei?",          "[SLATE] NU: Status = Fara Resursa"],
  ["6", "Aloca pe prima resursa cu slot disponibil",               "[GREEN] DA: Status = Planificat"],
], [25, 230, 210], { headerBg: C_DARK }));

// 7.4
children.push(h2("7.4 Exemplu concret"));
children.push(body("Comanda WO 8300001879 (client: exemplu) cu 4 operatii:"));
children.push(makeTable([
  ["Op",  "CL",   "Rank", "Durata", "Logica de alocare"],
  ["732", "MGN",  "1",    "0.2h",   "Rank 1, prima operatie. Nicio dependenta. Alocat pe 'Linie magneziu' pe 24.03. Status: Planificat."],
  ["715", "FAL",  "3",    "1.1h",   "Rank 3. Rank 1 = planificat (end=24.03), deci earliest_start=25.03. Alocat pe 'Stahl 1' pe 25.03. Status: Planificat."],
  ["880", "OPMP", "5",    "1.1h",   "Rank 5. Rank 3 = planificat (end=25.03), deci earliest_start=26.03. Alocat pe 'Persoana 1 OPMAN'. Status: Planificat."],
  ["777", "POL",  "4",    "1.2h",   "Rank 4. Rank 3 = planificat (end=25.03), deci earliest_start=26.03. Alocat pe resursa POL. Status: Planificat."],
], [28, 38, 32, 38, 329], { headerBg: C_DARK, fontSize: 18 }));

// 7.5
children.push(h2("7.5 Capacitatea resurselor"));
children.push(body("Fiecare resursa are un program definit pe zile cu numarul de ore disponibile si schimburile active. Exemplu: o masina cu schimburi '6-14;14-22' are 16 ore/zi disponibile. Algoritmul respecta strict aceste ore \u2013 nu programeaza mai multe ore decat sunt disponibile pe o resursa intr-o zi."));
children.push(body("Daca o operatie necesita mai multe ore decat are o zi, ea se distribuie pe mai multe zile consecutive (split). Exemplu: o operatie de 37h pe o resursa cu 16h/zi se va intinde pe 3 zile (16h + 16h + 5h)."));

// ── Build document ────────────────────────────────────────────────────────────

const doc = new Document({
  numbering,
  styles,
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_W, height: PAGE_H },
        margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          children: [
            new TextRun({ text: "Arta Grafica \u2013 Planificare Productie \u2013 Ghid de Utilizare", size: 18, color: C_SLATE, font: "Arial" }),
          ],
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1", space: 4 } },
          spacing: { after: 0 },
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          children: [
            new TextRun({ text: "Pagina ", size: 18, color: C_SLATE, font: "Arial" }),
            new TextRun({ children: [PageNumber.CURRENT], size: 18, color: C_SLATE, font: "Arial" }),
            new TextRun({ text: " din ", size: 18, color: C_SLATE, font: "Arial" }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, color: C_SLATE, font: "Arial" }),
          ],
          alignment: AlignmentType.CENTER,
          border: { top: { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1", space: 4 } },
          spacing: { before: 0 },
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  const out = "Ghid_Utilizare_Arta_Grafica.docx";
  fs.writeFileSync(out, buf);
  console.log("DOCX generat:", out);
}).catch(err => { console.error(err); process.exit(1); });
