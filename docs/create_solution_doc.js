/**
 * Genereaza Documentatie_Solutie_Arta_Grafica.docx
 * Ruleaza: node create_solution_doc.js
 */
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak, LevelFormat,
} = require("docx");
const fs = require("fs");

// ── Geometrie pagina A4 ───────────────────────────────────────────────────────
const PAGE_W  = 11906;
const PAGE_H  = 16838;
const MARGIN  = 1134;            // 2 cm
const CONTENT = PAGE_W - 2 * MARGIN;  // 9638 DXA

// ── Culori ────────────────────────────────────────────────────────────────────
const C_BLUE   = "3b82f6";
const C_DARK   = "1e293b";
const C_SLATE  = "475569";
const C_BG     = "f1f5f9";
const C_WHITE  = "FFFFFF";
const C_GREEN  = "16a34a";
const C_RED    = "dc2626";
const C_AMBER  = "d97706";
const C_ORANGE = "ea580c";
const C_PURPLE = "7c3aed";
const C_TEAL   = "0d9488";

// ── Utilitare ─────────────────────────────────────────────────────────────────

function body(text, opts = {}) {
  const runs = [];
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
    spacing: { after: 140 },
    alignment: AlignmentType.JUSTIFIED,
    ...opts.para,
  });
}

function bullet(text, level = 0) {
  const ref = level === 0 ? "bullets" : "bullets2";
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

function note(text) {
  return new Paragraph({
    children: [new TextRun({ text, italics: true, color: C_SLATE, size: 20 })],
    spacing: { before: 100, after: 180 },
    indent: { left: 500 },
    border: {
      left: { style: BorderStyle.SINGLE, size: 14, color: C_BLUE, space: 12 },
    },
  });
}

function noteGreen(text) {
  return new Paragraph({
    children: [new TextRun({ text, italics: true, color: "15803d", size: 20 })],
    spacing: { before: 100, after: 180 },
    indent: { left: 500 },
    border: {
      left: { style: BorderStyle.SINGLE, size: 14, color: C_GREEN, space: 12 },
    },
  });
}

function spacer(pts = 100) {
  return new Paragraph({ children: [], spacing: { after: pts } });
}

const CELL_BORDER = {
  top:    { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1" },
  bottom: { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1" },
  left:   { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1" },
  right:  { style: BorderStyle.SINGLE, size: 4, color: "CBD5E1" },
};

function scaleCols(pdfCols) {
  const pdfSum = pdfCols.reduce((a, b) => a + b, 0);
  const dxa = pdfCols.map(c => Math.round((c / pdfSum) * CONTENT));
  const diff = CONTENT - dxa.reduce((a, b) => a + b, 0);
  dxa[dxa.length - 1] += diff;
  return dxa;
}

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
          let color = isHeader ? C_WHITE : C_DARK;
          let bold = isHeader;
          let cleanText = String(text);
          const colorMatch = cleanText.match(/^\[([A-Z]+)\]\s*/);
          if (colorMatch) {
            const map = {
              RED: C_RED, GREEN: C_GREEN, AMBER: C_AMBER, ORANGE: C_ORANGE,
              SLATE: C_SLATE, BLUE: C_BLUE, PURPLE: C_PURPLE, TEAL: C_TEAL,
            };
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
              alignment: AlignmentType.LEFT,
            })],
          });
        }),
      });
    }),
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, bold: true, size: 40, color: C_BLUE, font: "Arial" })],
    spacing: { before: 400, after: 200 },
  });
}
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, bold: true, size: 30, color: C_DARK, font: "Arial" })],
    spacing: { before: 260, after: 160 },
  });
}
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text, bold: true, size: 24, color: C_SLATE, font: "Arial" })],
    spacing: { before: 180, after: 120 },
  });
}

// ─────────────────────────────────────────────────────────────────────────────
//  CONTINUT
// ─────────────────────────────────────────────────────────────────────────────

const children = [];

// ── Coperta ───────────────────────────────────────────────────────────────────
children.push(spacer(1800));
children.push(new Paragraph({
  children: [new TextRun({ text: "Arta Grafica", bold: true, size: 80, color: C_DARK, font: "Arial" })],
  alignment: AlignmentType.CENTER,
  spacing: { after: 80 },
}));
children.push(new Paragraph({
  children: [new TextRun({ text: "Planificare Productie", size: 52, color: C_BLUE, font: "Arial" })],
  alignment: AlignmentType.CENTER,
  spacing: { after: 500 },
}));
children.push(new Paragraph({
  children: [new TextRun({ text: "Documentatie Solutie Implementata", bold: true, size: 44, color: C_DARK, font: "Arial" })],
  alignment: AlignmentType.CENTER,
  spacing: { after: 200 },
}));
children.push(new Paragraph({
  children: [new TextRun({ text: "Versiunea 2.0 \u2013 Aprilie 2026", size: 26, color: C_SLATE, font: "Arial" })],
  alignment: AlignmentType.CENTER,
  spacing: { after: 0 },
}));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ── Cuprins ───────────────────────────────────────────────────────────────────
children.push(h1("Cuprins"));
children.push(makeTable([
  ["Nr.", "Capitol", "Descriere"],
  ["1.",  "Ce face aplicatia",              "Obiectiv, date folosite, module principale"],
  ["2.",  "Definitii si notiuni cheie",      "Termeni utilizati in aplicatie si in productie"],
  ["3.",  "Modulul Dashboard",               "Statistici, import date, rulare planificare"],
  ["4.",  "Modulul Comenzi",                 "Lista comenzilor cu rezumat planificare"],
  ["5.",  "Modulul Planificare",             "Rezultatele detaliate ale planificarii automate"],
  ["6.",  "Modulul Gantt",                   "Vizualizare temporala a operatiilor planificate"],
  ["7.",  "Modulul Board Masini",            "Vizualizare pe fiecare masina/resursa"],
  ["8.",  "Modulul Stoc Materiale",          "Situatia stocurilor, rezervari si aprovizionari"],
  ["9.",  "Algoritmul de Planificare",       "Cum functioneaza logica de alocare automata"],
  ["10.", "Mecanismul Frozen",               "Cum se blocheaza manual o operatie pe o pozitie"],
  ["11.", "Autentificare si securitate",     "Login, sesiune, credentiale"],
], [25, 145, 295], { headerBg: C_BLUE }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 1. Ce face aplicatia ─────────────────────────────────────────────────────
children.push(h1("1. Ce face aceasta aplicatie"));
children.push(body("Aplicatia **Arta Grafica \u2013 Planificare Productie** este un sistem web care ajuta tipografia sa isi planifice productia in mod automat si vizual."));
children.push(body("Pe scurt: primeste date din ERP (comenzi, operatii, stocuri, resurse), ruleaza un algoritm de planificare si arata grafic ce masina face ce operatie si cand."));

children.push(spacer(120));
children.push(h2("Problema rezolvata"));
children.push(body("Inainte de aceasta aplicatie, planificatorul trebuia sa raspunda manual la intrebari precum:"));
children.push(bullet("Cand poate incepe tiparirea comenzii X, daca masina Y este ocupata?"));
children.push(bullet("Care comenzi sunt blocate din lipsa materialelor?"));
children.push(bullet("Ce comenzi se livreaza cu intarziere?"));
children.push(bullet("Pe ce masina alochez operatia de faltuit pentru comanda Z?"));
children.push(spacer(100));
children.push(body("Aplicatia raspunde automat la toate aceste intrebari, afisand rezultatele intr-o interfata vizuala clara."));

children.push(spacer(120));
children.push(h2("Date folosite (surse)"));
children.push(body("Toate datele provin din fisiere Excel exportate din ERP. La fiecare import se incarca:"));
children.push(makeTable([
  ["Fisier / Sheet Excel", "Ce contine", "Se importa in"],
  ["Stari comenzi",        "Lista comenzilor de productie si vanzare, cu BT, stadiu prepress, date livrare", "Tabelul Comenzi"],
  ["Dispatch List",        "Operatiile fiecarei comenzi: cod CL, timpi de executie, cantitate executata", "Tabelul Dispatch"],
  ["Lista Deficit",        "Rezervarile si aprovizionarile de materiale per comanda", "Tabelul Deficit (Stoc)"],
  ["Lista Operatii (UDDB)","Catalogul operatiilor cu rank (ordinea de executie) si centru de lucru", "Tabelul Operatii"],
  ["Lista Resurse",        "Masinile si oamenii disponibili, cu centrele de lucru si operatiile acceptate", "Tabelul Resurse"],
  ["Program Resurse",      "Orele disponibile pe fiecare zi calendaristica, pentru fiecare resursa", "Tabelul Program Resurse"],
], [120, 200, 145], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(note("Aplicatia nu citeste direct din ERP. Operatorul exporta datele din ERP in Excel, le incarca in aplicatie prin butonul 'Import', iar aplicatia proceseaza datele si ruleaza planificarea."));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 2. Definitii si notiuni ──────────────────────────────────────────────────
children.push(h1("2. Definitii si notiuni cheie"));
children.push(body("Aceasta sectiune explica termenii tehnici utilizati in aplicatie si in documentatia de productie."));

children.push(h2("Tipuri de comenzi"));
children.push(makeTable([
  ["Termen", "Explicatie", "In aplicatie"],
  ["WO (Work Order)", "Numarul unic al comenzii de productie (ex: 7300003422)", "Coloana WO in Planificare si Comenzi"],
  ["CP (Comanda Productie)", "Identic cu WO. Numarul comenzii de productie.", "Coloana CP in Comenzi"],
  ["CV (Comanda Vanzare)", "Comanda de vanzare corespondenta. Nu toate CP-urile au un CV.", "Coloana CV in Comenzi"],
  ["Status Comanda", "LIBER = comanda activa. STOP = comanda suspendata, exclusa din planificare.", "Filtru si badge in Comenzi"],
  ["Stadiu Prepress", "Faza de pregatire a fisierelor de tipar. 06 = cel mai avansat (in productie).", "Badge colorat in Comenzi"],
], [110, 220, 135], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(h2("Operatii si resurse"));
children.push(makeTable([
  ["Termen", "Explicatie"],
  ["OP (Operatie)", "O etapa din procesul de productie: ex. tipar, faltuit, ambalat. Fiecare are un cod unic (ex: 715)."],
  ["CL (Centru de Lucru)", "Grupul de masini care pot executa un tip de operatie (ex: FAL = faltuire, SM = matritare)."],
  ["Resursa", "O masina sau o persoana concreta din cadrul unui CL (ex: 'Stahl 1' in CL FAL)."],
  ["Rank", "Ordinea de executie a operatiilor in cadrul unei comenzi. Rank 1 = prima operatie, rank 3 = se executa dupa rank 1 si 2."],
  ["Durata (h)", "Orele necesare pentru a executa operatia. Calculat ca: P_Setup + P_Runtime - R_Runtime (cat s-a executat deja)."],
], [110, 355], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(h2("Date calendaristice"));
children.push(makeTable([
  ["Termen", "Explicatie"],
  ["Data Livrare", "Data la care comanda trebuie livrata clientului. Poate fi 'actualizata' daca BT-ul a intarziat."],
  ["Data Limita BT", "Data maxima pana la care clientul trebuie sa aprobe Bunul de Tipar (BT). Agreata contractual."],
  ["BT (Bun de Tipar)", "Aprobarea scrisa a clientului pentru inceperea tiparului. Fara BT, operatiile nu pot fi planificate."],
  ["Data Planificare", "Data estimata la care comanda va fi finalizata, conform algoritmului de planificare."],
  ["Intarziere (zile)", "Diferenta dintre Data Planificare si Data Livrare. Pozitiv = intarziat, negativ = in avans."],
], [120, 345], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(h2("Stocuri si materiale"));
children.push(makeTable([
  ["Termen", "Formula / Explicatie"],
  ["Sold Actual", "Cantitatea fizica existenta in stoc la momentul exportului din ERP."],
  ["Rezervat", "Cantitatea alocata comenzilor de productie active (tip B in deficit). Poate fi negativa in ERP."],
  ["Disponibil", "Sold Actual + Rezervat. Poate fi negativ daca mai multe comenzi rezerva mai mult decat exista."],
  ["APROV. (Aprovizionare)", "Cantitatea care va intra in stoc din comenzi de achizitie sau productie (tip A in deficit)."],
  ["Disponibil Final", "Disponibil + Aprovizionare. Reflecta situatia dupa ce intra si aprovizionarile planificate."],
], [120, 345], { headerBg: C_BLUE }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 3. Dashboard ─────────────────────────────────────────────────────────────
children.push(h1("3. Modulul Dashboard"));
children.push(body("Dashboard-ul este prima pagina vazuta la autentificare. Ofera o privire rapida asupra situatiei productiei si permite executarea actiunilor principale: import date si rulare planificare."));

children.push(h2("Carduri statistice"));
children.push(makeTable([
  ["Card", "Ce arata"],
  ["Total Comenzi",      "Numarul total de comenzi importate (inclusiv cele STOP)"],
  ["Comenzi Active",     "Comenzile cu status LIBER, eligibile pentru planificare"],
  ["Comenzi STOP",       "Comenzile suspendate, excluse din algoritm"],
  ["Operatii Dispatch",  "Total operatii din listele de dispatch (volumul de munca)"],
  ["Resurse",            "Numarul de masini/persoane configurate pentru planificare"],
], [130, 335], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(h2("Actiuni principale"));
children.push(body("**Import Date Excel** \u2013 Incarca toate fisierele Excel intr-o singura operatie. Aplicatia sterge datele vechi si incarca datele noi. Dureaza cateva secunde. Se recomanda rulat dupa fiecare export din ERP."));
children.push(spacer(80));
children.push(body("**Ruleaza Planificarea** \u2013 Porneste algoritmul de planificare. Analizeaza toate comenzile active, verifica BT, materiale, dependente de rank si disponibilitatea resurselor, apoi aloca operatiile pe masini. La final, tab-urile Planificare, Gantt si Board Masini se actualizeaza cu rezultatele."));

children.push(spacer(120));
children.push(h2("Grafice"));
children.push(body("Sub carduri si butoane se afiseaza doua grafice:"));
children.push(bullet("**Distributia pe Stadiu Prepress** \u2013 Arata cate comenzi sunt in fiecare faza (01-Fara Fisiere pana la 06-In productie). Ajuta la evaluarea incarcaturii pregatirii de productie."));
children.push(bullet("**Ultima sesiune de planificare** \u2013 Data, ora si rezultatele numerice ale ultimei rulari: cate operatii planificate, cate blocate si din ce motive."));

children.push(spacer(120));
children.push(h2("Asistentul AI"));
children.push(body("In dreapta paginii se afla un asistent conversational bazat pe Claude AI. Poate raspunde la intrebari despre situatia productiei, analiza blocajele, identifica comenzile urgente si sugera actiuni de remediere. Raspunsurile sunt generate pe baza datelor reale din sistem."));
children.push(note("Asistentul AI functioneaza doar daca serverul are acces la internet si cheia API Anthropic este configurata corect in fisierul .env."));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 4. Comenzi ───────────────────────────────────────────────────────────────
children.push(h1("4. Modulul Comenzi"));
children.push(body("Tab-ul Comenzi afiseaza lista tuturor comenzilor de productie importate, cu informatii detaliate despre statusul planificarii si al materialelor. Este principalul punct de vedere pentru a intelege situatia fiecarei comenzi."));

children.push(h2("Coloanele tabelului"));
children.push(makeTable([
  ["Coloana", "Descriere"],
  ["CP",              "Numarul comenzii de productie (Work Order)"],
  ["CV",              "Numarul comenzii de vanzare corespondente (daca exista)"],
  ["Client",          "Numele clientului"],
  ["Articol",         "Produsul care se fabrica"],
  ["Tip",             "Vanzare (V) sau Productie (P)"],
  ["Stadiu Prepress", "Faza de pregatire a fisierelor (06 = gata de productie)"],
  ["Status",          "LIBER sau STOP"],
  ["Cant.",           "Cantitatea din comanda"],
  ["Data Livrare",    "Data la care trebuie livrata comanda"],
  ["Data Plan.",      "Data estimata de finalizare conform planificarii automate"],
  ["Intarziere",      "Diferenta fata de data livrare (rosu = intarziat, verde = in termen)"],
  ["St. Plan.",       "Statusul global al planificarii (Planificat, Previzionat, Partial, Blocat)"],
  ["St. Material",    "Disponibilitatea materialelor (Disponibil, In aprovizionare, Lipsa)"],
  ["Plata",           "Achitat sau Neachitat, calculat din valoarea de platit vs. valoarea platita"],
], [100, 365], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(h2("Statusul planificarii per comanda"));
children.push(makeTable([
  ["Status Planificare", "Culoare", "Semnificatie"],
  ["Planificat",   "[GREEN] Verde",  "Toate operatiile comenzii au fost alocate pe masini cu date de start/stop"],
  ["Previzionat",  "[BLUE] Albastru","Operatiile sunt alocate pe masini, dar cu o data de start viitoare (comanda asteapta BT sau aprovizionare material)"],
  ["Partial",      "[TEAL] Cyan",   "Unele operatii sunt planificate/previzionate, altele blocate"],
  ["Blocat",       "[RED] Rosu",    "Nicio operatie nu a putut fi planificata (lipsa BT fara data, lipsa material fara aprovizionare)"],
], [100, 100, 265], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(h2("Statusul materialelor per comanda"));
children.push(makeTable([
  ["Status Material", "Culoare", "Semnificatie"],
  ["Disponibil",       "[GREEN] Verde",    "Stocul existent acopera necesarul comenzii"],
  ["In aprovizionare", "[ORANGE] Portocaliu","Stocul existent nu este suficient, dar o aprovizionare viitoare acopera deficitul"],
  ["Lipsa",            "[RED] Rosu",       "Nici stocul existent, nici aprovizionarile planificate nu acopera necesarul"],
], [120, 120, 225], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(h2("Functii de cautare si filtrare"));
children.push(bullet("**Cautare text** \u2013 Cauta dupa numarul CP, CV, client sau articol"));
children.push(bullet("**Filtru status** \u2013 Afiseaza doar comenzile LIBER sau STOP"));
children.push(bullet("**Carduri statistice** \u2013 Clickabile pentru filtrare rapida (Total, 06 In productie, LIBER, STOP)"));
children.push(bullet("**Expandare rand** \u2013 Click pe sageata din stanga unui rand afiseaza toate operatiile dispatch aferente comenzii, cu timpii de executie"));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 5. Planificare ───────────────────────────────────────────────────────────
children.push(h1("5. Modulul Planificare"));
children.push(body("Tab-ul Planificare afiseaza detaliat fiecare operatie din Dispatch List, cu rezultatul alocarii automate: pe ce masina a fost programata, cand incepe si cand se termina, sau de ce nu a putut fi planificata."));

children.push(h2("Cardurile statistice"));
children.push(body("Cardurile din partea de sus arata intotdeauna totalurile reale din baza de date (nu din pagina curenta). Sunt clickabile pentru filtrare rapida:"));
children.push(makeTable([
  ["Card", "Culoare", "Semnificatie"],
  ["Total afisate",  "Gri",          "Numarul total de operatii in sesiunea curenta de planificare"],
  ["Planificate",    "[GREEN] Verde", "Operatii cu resursa si date de start/stop alocate"],
  ["Previzionate",   "[BLUE] Albastru","Operatii alocate pe masini dar cu start in viitor (asteapta BT sau material)"],
  ["Fara Material",  "[RED] Rosu",   "Materialele necesare comenzii sunt insuficiente si nu exista aprovizionare"],
  ["Fara BT",        "[ORANGE] Portocaliu","Comanda nu are Bun de Tipar si nici data limita BT configurata"],
  ["Blocate Rank",   "[AMBER] Galben","O operatie anterioara (rank inferior) nu este inca planificata"],
  ["Fara Resursa",   "Gri",          "Nicio masina din centrul de lucru nu are ore disponibile"],
], [100, 120, 245], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(note("Cardul Planificate afiseaza si numarul total de ore alocate, adunat din toate operatiile planificate si previzionate."));

children.push(h2("Coloanele tabelului"));
children.push(makeTable([
  ["Coloana", "Descriere"],
  ["WO",         "Numarul comenzii de productie"],
  ["OP",         "Codul operatiei (ex: 715 = faltuit)"],
  ["CL",         "Centrul de lucru (tipul masinii)"],
  ["Resursa",    "Masina sau persoana alocata (afisat doar pentru Planificat si Previzionat)"],
  ["Status",     "Rezultatul planificarii (badge colorat)"],
  ["Freeze",     "Buton de blocare a pozitiei operatiei (vezi capitolul 10)"],
  ["Start",      "Data si ora de inceput planificate"],
  ["End",        "Data si ora de sfarsit planificate"],
  ["Durata (h)", "Ore ramase de executat"],
  ["Motiv",      "Explicatia pentru operatiile neplanificate"],
], [80, 385], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(h2("Indicatorul de operatie Frozen"));
children.push(body("O operatie cu statusul **Planificat** sau **Previzionat** poate fi 'inghetata' (frozen). Operatiile frozen apar cu un simbol ❄ inainte de badge-ul de status si au butonul de Freeze colorat in mov. La urmatoarea rulare a planificarii, aceste operatii sunt copiate nemodificate in noua sesiune."));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 6. Gantt ─────────────────────────────────────────────────────────────────
children.push(h1("6. Modulul Gantt"));
children.push(body("Tab-ul Gantt afiseaza o diagrama clasica de tip Gantt cu toate operatiile planificate. Fiecare bara orizontala reprezinta o operatie, cu lungimea proportionala cu durata, pozitionata in timp pe axa orizontala. Dependentele dintre operatii sunt afisate ca sageti."));

children.push(h2("Navigare"));
children.push(makeTable([
  ["Actiune", "Efect"],
  ["Scroll orizontal",  "Navigheaza in timp (stanga = trecut, dreapta = viitor)"],
  ["Scroll vertical",   "Deruleaza lista operatiilor"],
  ["Buton Day/Week/Month", "Schimba granularitatea axei temporale"],
  ["Buton Today",       "Sare la data curenta"],
  ["Filtru CL",         "Afiseaza doar operatiile din centrul de lucru selectat"],
  ["Cautare WO",        "Afiseaza doar operatiile comenzii cu numarul WO cautat"],
], [140, 325], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(h2("Coduri culori in Gantt"));
children.push(makeTable([
  ["Culoare", "Semnificatie"],
  ["[BLUE] Albastru", "Operatie planificata, in termen fata de data livrarii"],
  ["[RED] Rosu",      "Operatie planificata, dar cu data de sfarsit depasita (intarziata)"],
  ["[PURPLE] Mov",    "Operatie Frozen (pozitia este blocata manual)"],
], [120, 345], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(body("Sagetile dintre bare indica dependentele: o bara poate incepe doar dupa terminarea barei anterioare la care pointeaza sageata. Aceasta reflecta logica de Rank din algoritm."));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 7. Board Masini ──────────────────────────────────────────────────────────
children.push(h1("7. Modulul Board Masini"));
children.push(body("Board Masini este o vizualizare centrata pe resurse: fiecare linie a tabelului reprezinta o masina sau o persoana, iar pe axa orizontala se vede un calendar cu ore. Operatiile apar ca bare colorate pe masina alocata."));
children.push(body("Aceasta vizualizare este ideala pentru a vedea incarcarea fiecarei masini si a identifica masini libere sau supraincarcate."));

children.push(h2("Navigare"));
children.push(makeTable([
  ["Actiune", "Efect"],
  ["Scroll cu rotita mouse",  "Navigheaza stanga/dreapta pe axa timpului"],
  ["Ctrl + Scroll (zoom)",    "Mareste sau micsoreaza intervalul de timp vizibil"],
  ["Drag (click + trage)",    "Pan liber in orice directie pe canvas"],
  ["Buton Azi",               "Navigheaza la data si ora curenta"],
  ["Filtru Centru de Lucru",  "Afiseaza doar masinile din CL selectat"],
], [140, 325], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(h2("Informatii vizuale"));
children.push(bullet("**Bara rosie verticala** \u2013 Indica ora exacta curenta (ca un cursor de timp)"));
children.push(bullet("**Tooltip la hover** \u2013 La trecerea mouse-ului peste o bara, apare un popup cu: WO, OP, client, articol, ora start, ora end, durata"));
children.push(bullet("**Coduri culori** \u2013 La fel ca in Gantt: Albastru = planificat si in termen, Rosu = intarziat, Mov = Frozen"));
children.push(bullet("**Badge-uri** \u2013 In coltul dreapta sus apar: numarul de masini vizibile, operatii totale planificate, operatii intarziate"));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 8. Stoc Materiale ────────────────────────────────────────────────────────
children.push(h1("8. Modulul Stoc Materiale"));
children.push(body("Tab-ul Stoc Materiale afiseaza situatia stocurilor de materii prime. Este esential pentru intelegerea motivului pentru care unele comenzi sunt blocate (status 'Fara Material' sau 'Lipsa')."));

children.push(h2("Coloanele tabelului"));
children.push(makeTable([
  ["Coloana", "Formula / Sursa", "Interpretare"],
  ["Articol",        "Cod articol ERP",                    "Codul unic al materiei prime"],
  ["Sold Actual",    "Din ERP",                            "Cantitatea fizica existenta in stoc"],
  ["Total Rezervat", "Suma rezervarilor tip B (negative)", "Cat este alocat comenzilor active"],
  ["Disponibil",     "Sold + Total Rezervat",              "Stocul real disponibil (poate fi negativ)"],
  ["APROV.",         "Suma aprovizionarilor tip A",        "Ce intra din comenzi de achizitie/productie"],
  ["Disp. Final",    "Disponibil + APROV.",               "Situatia dupa ce intra si aprovizionarile"],
  ["Status",         "Calculat din Disp. Final",          "Deficit / In aprovizionare / Epuizat / Disponibil"],
], [80, 140, 245], { headerBg: C_BLUE, fontSize: 18 }));

children.push(spacer(120));
children.push(h2("Coduri culori Status"));
children.push(makeTable([
  ["Status", "Culoare", "Conditie", "Actiune recomandata"],
  ["Deficit",          "[RED] Rosu",          "Disponibil Final < 0",       "Urgenta aprovizionare"],
  ["In aprovizionare", "[BLUE] Albastru",     "Disponibil < 0 dar Disp.Final \u2265 0", "Asteapta aprovizionare planificata"],
  ["Epuizat",          "[AMBER] Galben",      "Disponibil = 0",              "Stoc zero, fara rezervari"],
  ["Disponibil",       "[GREEN] Verde",       "Disponibil > 0",              "Situatie normala"],
], [100, 100, 160, 105], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(h2("Carduri statistice"));
children.push(body("Cele 5 carduri din partea de sus arata: Total articole, Disponibil (verde), In aprovizionare (albastru), Epuizat (galben), Deficit (rosu). Fiecare card este clickabil si filtreaza tabelul."));
children.push(spacer(80));
children.push(note("Articolele cu status 'Deficit' (rosu) sunt cauza directa a operatiilor marcate 'Fara Material' in tab-ul Planificare. Aprovizionarea acestor articole va debloca planificarea comenzilor respective."));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 9. Algoritmul de Planificare ─────────────────────────────────────────────
children.push(h1("9. Algoritmul de Planificare"));
children.push(body("Algoritmul de planificare este 'creierul' aplicatiei. Primeste datele importate si produce o alocare optima a operatiilor pe masini, respectand toate constrangerile reale."));
children.push(body("Algoritmul ruleaza la apasarea butonului 'Ruleaza Planificarea' din Dashboard. Creeaza o noua sesiune de planificare cu timestamp, planifica toate comenzile active si salveaza rezultatele in baza de date."));

children.push(h2("9.1 Pasul 0: Operatii Frozen (blocate manual)"));
children.push(body("Inainte de orice altceva, algoritmul verifica daca exista operatii marcate ca Frozen in sesiunea precedenta. Daca da, aceste operatii sunt copiate identic in noua sesiune (aceeasi masina, aceleasi date de start/stop) si orele lor sunt pre-rezervate din capacitatea masinilor."));
children.push(body("Acest mecanism garanteaza ca operatiile fixate manual de planificator nu sunt modificate de planificarea automata."));

children.push(spacer(120));
children.push(h2("9.2 Pasul 1: Ordonarea comenzilor"));
children.push(body("Comenzile nu sunt procesate aleator. Ordinea determina care comenzi primesc resurse si materiale primele (prioritate mai mare = resurse mai bune):"));
children.push(makeTable([
  ["Prioritate", "Criteriu", "Rationament"],
  ["1 (maxima)", "Stadiu Prepress avansat", "Comenzile gata de productie (06) se planifica primele"],
  ["2",          "Data livrare mai apropiata", "In caz de egalitate la stadiu, comanda cu livrare mai apropiata are prioritate"],
  ["Exclus",     "Status STOP", "Nu se planifica deloc comenzile suspendate"],
], [80, 170, 215], { headerBg: C_DARK }));

children.push(spacer(100));
children.push(note("Prioritatile de Stadiu Prepress: 06-In productie (100p) > 05-BT existent (50p) > 04-Trimis la BT (40p) > 03-Fisiere existente (30p) > 02-Job creat (20p) > 01-Fara Fisiere (10p) > 00-N/A (0p)."));

children.push(spacer(120));
children.push(h2("9.3 Pasul 2: Verificarile per comanda"));
children.push(body("Pentru fiecare comanda, operatiile sunt procesate in ordinea rank-ului (de la cea mai mica valoare \u2013 prima operatie, la cea mai mare \u2013 ultima operatie). Fiecare comanda trece prin mai multe verificari inainte de a i se aloca o resursa:"));

children.push(h3("A. Verificarea BT (Bun de Tipar)"));
children.push(body("Se verifica daca comanda are cel putin un camp BT completat si valid (BT1, BT2, BT3 sau BT4, diferit de data invalida 1911-11-11)."));
children.push(makeTable([
  ["Situatie", "Rezultat"],
  ["Are BT valid", "Continua la urmatoarea verificare"],
  ["Nu are BT, dar are Data Limita BT", "[BLUE] PREVIZIONAT \u2013 operatiile se planifica pe masini, dar nu pot incepe mai devreme de Data Limita BT"],
  ["Nu are BT si nici Data Limita BT", "[ORANGE] Fara BT \u2013 toate operatiile comenzii sunt blocate"],
], [160, 305], { headerBg: C_DARK }));

children.push(spacer(120));
children.push(h3("B. Verificarea Materialelor"));
children.push(body("Se verifica daca materialele necesare comenzii sunt disponibile in stoc. Verificarea se face la nivel de comanda (WO), nu per operatie."));
children.push(body("Algoritmul simuleaza consumul secvential: pe masura ce comenzile cu prioritate mai mare sunt planificate, ele 'consuma' din stocul disponibil. Comenzile cu prioritate mai mica pot gasi stocul redus."));
children.push(makeTable([
  ["Situatie", "Rezultat"],
  ["Stoc suficient", "Continua la urmatoarea verificare. Cantitatea este rezervata (scazuta din stoc)."],
  ["Stoc insuficient, dar exista aprovizionari viitoare care acopera deficitul", "[BLUE] PREVIZIONAT \u2013 data de start nu poate fi mai devreme decat data sosirii materialului"],
  ["Stoc insuficient si aprovizionarile viitoare nu acopera deficitul", "[RED] Fara Material \u2013 toate operatiile comenzii sunt blocate"],
], [200, 265], { headerBg: C_DARK }));

children.push(spacer(80));
children.push(note("Daca o comanda intra pe calea Previzionat din ambele motive (lipsa BT si lipsa material), data de start va fi cea mai tarzie dintre 'Data Limita BT' si 'data sosirii materialului'."));

children.push(spacer(120));
children.push(h3("C. Verificarea Rank (dependente intre operatii)"));
children.push(body("Operatiile dintr-o comanda au un Rank care defineste ordinea de executie. O operatie de Rank N nu poate incepe pana cand toate operatiile de Rank < N nu sunt cel putin planificate."));
children.push(makeTable([
  ["Starea operatiei precedente (rank inferior)", "Efect asupra operatiei curente"],
  ["Completata (remaining = 0 ore)",              "Nicio restrictie. Se poate planifica imediat."],
  ["Planificata sau Previzionata (alerta pe masina)", "Se poate planifica, dar va incepe a doua zi dupa sfarsitul operatiei precedente."],
  ["Deschisa (neplanificata, blocata)",           "[AMBER] Blocata Rank \u2013 nu se poate planifica pana nu se rezolva operatia precedenta."],
], [200, 265], { headerBg: C_DARK }));

children.push(spacer(100));
children.push(note("Daca mai multe operatii impart acelasi Rank, se ia in considerare cea mai restrictiva: daca macar una este 'deschisa', toate operatiile cu Rank superior sunt blocate. Daca sunt planificate, data de start a urmatorului Rank este dupa cea mai tarzie data de sfarsit dintre toate operatiile de la Rank-ul curent."));

children.push(spacer(120));
children.push(h3("D. Alocarea pe Resursa"));
children.push(body("Daca toate verificarile au trecut, algoritmul cauta o masina disponibila in centrul de lucru al operatiei:"));
children.push(makeTable([
  ["Pas", "Ce se intampla"],
  ["1", "Se calculeaza durata ramasa: P_Setup + P_Runtime - R_Runtime (orele deja executate se scad)"],
  ["2", "Se identifica resursele din CL-ul operatiei care pot executa acel cod de operatie"],
  ["3", "Pentru fiecare resursa, se cauta prima zi cu ore disponibile, incepand de la 'earliest_start'"],
  ["4", "Orele se aloca pe zile consecutive pana la epuizarea duratei necesare (operatia poate fi distribuita pe mai multe zile)"],
  ["5", "Orele alocate se scad din capacitatea resursei (nu mai sunt disponibile pentru alte operatii)"],
  ["6", "Daca nicio resursa nu are ore disponibile: [SLATE] Fara Resursa"],
], [30, 435], { headerBg: C_DARK }));

children.push(spacer(120));
children.push(h2("9.4 Schema decizionala rezumata"));
children.push(body("Fluxul complet de decizie pentru fiecare operatie:"));
children.push(makeTable([
  ["#", "Intrebare", "NU \u2192 Rezultat", "DA \u2192 Continuare"],
  ["0", "Operatia este Frozen?",                              "\u2013",                "Copiere directa. Skip restul.",       ],
  ["1", "Operatia este deja terminata? (remaining=0)",        "\u2013",                "Skip (completata)."],
  ["2", "Comanda are BT valid?",                              "Fara BT sau Previzionat", "Verif. 3"],
  ["3", "Materialele sunt disponibile?",                      "Fara Material sau Previzionat", "Verif. 4"],
  ["4", "Operatiile anterioare (rank inferior) sunt planif.?","Blocata Rank",          "Verif. 5"],
  ["5", "Exista resursa cu ore disponibile?",                 "Fara Resursa",          "Aloca pe resursa. Status: Planificat sau Previzionat"],
], [20, 185, 145, 115], { headerBg: C_DARK, fontSize: 18 }));

children.push(spacer(120));
children.push(h2("9.5 Tipuri de planificare"));
children.push(makeTable([
  ["Tip", "Culoare", "Conditii"],
  ["Planificat",  "[GREEN] Verde",       "Are BT + materiale + resursa disponibila incepand de azi. Data de start este cat mai devreme posibil."],
  ["Previzionat", "[BLUE] Albastru",    "Lipseste BT sau material, dar situatia se rezolva la o data viitoare cunoscuta. Data de start este dupa rezolvarea blocajului."],
  ["Fara BT",     "[ORANGE] Portocaliu","Nu are BT si nici data limita BT. Nimeni nu stie cand va fi aprobat."],
  ["Fara Material","[RED] Rosu",        "Nu are materialele necesare si nici aprovizionare planificata suficienta."],
  ["Blocata Rank", "[AMBER] Galben",    "O operatie anterioara (rank inferior) nu este inca planificata."],
  ["Fara Resursa", "Gri",              "Nicio masina din CL-ul operatiei nu are ore disponibile in orizontul de planificare."],
], [90, 100, 275], { headerBg: C_BLUE }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 10. Mecanismul Frozen ────────────────────────────────────────────────────
children.push(h1("10. Mecanismul Frozen (Blocare Manuala)"));
children.push(body("Mecanismul Frozen permite planificatorului sa fixeze manual pozitia unei operatii pe o resursa si la o data anumita, astfel incat planificarea automata sa nu o mute la urmatoarea rulare."));
children.push(body("Aceasta este utila atunci cand planificatorul cunoaste informatii contextuale (ex: un client a cerut explicit o anumita data, masina X este singura disponibila pentru o lucrare speciala etc.) pe care algoritmul automat nu le poate deduce din date."));

children.push(h2("Cum se foloseste"));
children.push(makeTable([
  ["Pas", "Actiune", "Detalii"],
  ["1", "Mergi in tab-ul Planificare", "Cauta operatia dorita dupa WO sau filtreaza dupa CL"],
  ["2", "Apasa butonul 'Freeze' din coloana Freeze", "Butonul este vizibil doar pentru operatiile cu status Planificat sau Previzionat"],
  ["3", "Operatia este acum Frozen", "Badge-ul de status afiseaza simbolul ❄ inainte. Butonul devine mov ('❄ Frozen')."],
  ["4", "La urmatoarea rulare a planificarii", "Operatia este copiata identic in noua sesiune (aceeasi masina, aceleasi date de start si end)"],
  ["5", "Pentru a debloca", "Apasa din nou butonul ('❄ Frozen') \u2013 operatia revine la planificarea automata la urmatoarea rulare"],
], [30, 140, 295], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(h2("Ce garanteaza mecanismul Frozen"));
children.push(bullet("Masina si datele de start/stop ale operatiei raman identice intre sesiuni de planificare."));
children.push(bullet("Orele rezervate de operatiile Frozen sunt pre-alocate la inceputul fiecarei sesiuni de planificare, astfel incat alte operatii nu pot fi programate in acelasi slot."));
children.push(bullet("Statusul (Planificat sau Previzionat) este pastrat identic din sesiunea in care s-a facut Freeze."));
children.push(bullet("Dependentele de Rank sunt respectate: operatiile de Rank superior ce urmeaza dupa o operatie Frozen vor folosi data de sfarsit a operatiei Frozen ca punct de start."));

children.push(spacer(120));
children.push(h2("Limitari si precautii"));
children.push(body("**Operatiile blocate (Fara Material, Fara BT etc.) nu pot fi Frozen.** Mecanismul Frozen functioneaza doar pentru operatii cu resursa si date alocate."));
children.push(body("**Daca o operatie Frozen are date in trecut**, ea apare cu culoarea rosie in Gantt si Board Masini (intarziata), dar pozitia sa nu se modifica la replanificare."));
children.push(note("Recomandat: dupa rezolvarea unui blocaj (ex: a sosit materialul, a fost aprobat BT-ul), verifica daca operatiile anterioare care s-au deblocat nu trebuie mutate manual inainte de a rula din nou planificarea."));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ─── 11. Autentificare si securitate ─────────────────────────────────────────
children.push(h1("11. Autentificare si securitate"));
children.push(body("Aplicatia este protejata prin autentificare cu utilizator si parola. Toate endpoint-urile API necesita un token valid."));

children.push(h2("Login"));
children.push(body("La accesarea aplicatiei se afiseaza pagina de login cu campurile Utilizator si Parola. Dupa autentificare cu succes, token-ul este salvat local in browser. Bifand 'Tine-ma minte', sesiunea persista si dupa inchiderea tab-ului."));
children.push(body("Pentru a te deconecta, apasa butonul 'Logout' din coltul dreapta sus."));

children.push(spacer(120));
children.push(h2("Credentiale implicite"));
children.push(makeTable([
  ["Camp", "Valoare implicita", "Observatie"],
  ["Utilizator", "andrei",    "Poate fi schimbat prin variabila de mediu AG_USER"],
  ["Parola",     "sarbu1234", "Poate fi schimbata prin variabila de mediu AG_PASS"],
  ["Salt token", "arta-grafica-2026", "Poate fi schimbat prin variabila de mediu AG_SALT"],
], [90, 120, 255], { headerBg: C_BLUE }));

children.push(spacer(120));
children.push(note("Recomandat pentru medii de productie: configurati credentiale puternice prin variabile de mediu in fisierul de serviciu systemd. Credentialele implicite sunt pentru dezvoltare si testare."));

children.push(spacer(200));
children.push(new Paragraph({
  children: [new TextRun({ text: "Sfarsit document", italics: true, color: C_SLATE, size: 20 })],
  alignment: AlignmentType.CENTER,
}));

// ── Numerotare ────────────────────────────────────────────────────────────────
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
    {
      reference: "bullets2",
      levels: [{
        level: 0, format: LevelFormat.BULLET, text: "\u25E6",
        alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 900, hanging: 300 } } },
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
      run: { size: 40, bold: true, font: "Arial", color: C_BLUE },
      paragraph: { spacing: { before: 400, after: 200 }, outlineLevel: 0 },
    },
    {
      id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { size: 30, bold: true, font: "Arial", color: C_DARK },
      paragraph: { spacing: { before: 260, after: 160 }, outlineLevel: 1 },
    },
    {
      id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
      run: { size: 24, bold: true, font: "Arial", color: C_SLATE },
      paragraph: { spacing: { before: 180, after: 120 }, outlineLevel: 2 },
    },
  ],
};

// ── Generare document ─────────────────────────────────────────────────────────
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
          children: [new TextRun({
            text: "Arta Grafica \u2013 Planificare Productie \u2013 Documentatie Solutie",
            size: 18, color: C_SLATE, font: "Arial",
          })],
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
  const out = "Documentatie_Solutie_Arta_Grafica.docx";
  fs.writeFileSync(out, buf);
  console.log("DOCX generat:", out);
}).catch(err => { console.error(err); process.exit(1); });
