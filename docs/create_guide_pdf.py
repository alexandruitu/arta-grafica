"""
Generate Ghid Utilizare PDF for Arta Grafica Production Planning.
Uses reportlab to create a professional user guide in Romanian.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
    KeepTogether, HRFlowable, ListFlowable, ListItem,
)

OUTPUT = "Ghid_Utilizare_Arta_Grafica.pdf"

# Colors
BLUE = HexColor("#3b82f6")
DARK = HexColor("#1e293b")
SLATE = HexColor("#475569")
LIGHT_BG = HexColor("#f1f5f9")
GREEN = HexColor("#16a34a")
RED = HexColor("#dc2626")
AMBER = HexColor("#d97706")
ORANGE = HexColor("#ea580c")

def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    styles = getSampleStyleSheet()

    # Custom styles
    styles.add(ParagraphStyle(
        'DocTitle', parent=styles['Title'],
        fontSize=28, leading=34, textColor=DARK, alignment=TA_CENTER,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        'DocSubtitle', parent=styles['Normal'],
        fontSize=14, leading=18, textColor=SLATE, alignment=TA_CENTER,
        spaceAfter=30,
    ))
    styles.add(ParagraphStyle(
        'H1', parent=styles['Heading1'],
        fontSize=20, leading=26, textColor=BLUE, spaceBefore=20, spaceAfter=12,
        borderWidth=0, borderPadding=0,
    ))
    styles.add(ParagraphStyle(
        'H2', parent=styles['Heading2'],
        fontSize=15, leading=20, textColor=DARK, spaceBefore=14, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        'H3', parent=styles['Heading3'],
        fontSize=12, leading=16, textColor=SLATE, spaceBefore=10, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        'Body', parent=styles['Normal'],
        fontSize=10.5, leading=15, textColor=DARK, alignment=TA_JUSTIFY,
        spaceAfter=8,
    ))
    styles['Bullet'].fontSize = 10.5
    styles['Bullet'].leading = 15
    styles['Bullet'].textColor = DARK
    styles['Bullet'].leftIndent = 20
    styles['Bullet'].bulletIndent = 8
    styles['Bullet'].spaceAfter = 4
    styles.add(ParagraphStyle(
        'Note', parent=styles['Normal'],
        fontSize=9.5, leading=14, textColor=SLATE, leftIndent=15,
        borderWidth=1, borderColor=BLUE, borderPadding=8,
        backColor=HexColor("#eff6ff"), spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        'StatusPlanned', parent=styles['Normal'],
        fontSize=10, textColor=GREEN, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'StatusBlocked', parent=styles['Normal'],
        fontSize=10, textColor=RED, alignment=TA_CENTER,
    ))

    # Cell styles for tables
    cell_style = ParagraphStyle('Cell', parent=styles['Normal'],
        fontSize=10, leading=13, textColor=DARK)
    cell_style_sm = ParagraphStyle('CellSm', parent=styles['Normal'],
        fontSize=9, leading=12, textColor=DARK)
    cell_hdr = ParagraphStyle('CellHdr', parent=styles['Normal'],
        fontSize=10, leading=13, textColor=white, fontName='Helvetica-Bold')
    cell_hdr_dark = ParagraphStyle('CellHdrDark', parent=styles['Normal'],
        fontSize=9.5, leading=13, textColor=white, fontName='Helvetica-Bold')

    def P(text, style=cell_style):
        """Wrap text in Paragraph for table cells (enables word-wrap)."""
        return Paragraph(str(text), style)

    def Ph(text):
        """Header cell."""
        return Paragraph(str(text), cell_hdr)

    def Phd(text):
        """Dark header cell."""
        return Paragraph(str(text), cell_hdr_dark)

    def Ps(text):
        """Small cell."""
        return Paragraph(str(text), cell_style_sm)

    story = []

    # ═══════════════════════════════════════════════════════════════
    # COVER PAGE
    # ═══════════════════════════════════════════════════════════════
    story.append(Spacer(1, 80))
    story.append(Paragraph("Arta Grafica", styles['DocTitle']))
    story.append(Paragraph("Planificare Productie", styles['DocSubtitle']))
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="60%", thickness=2, color=BLUE, spaceAfter=20))
    story.append(Spacer(1, 20))
    story.append(Paragraph("Ghid de Utilizare", ParagraphStyle(
        'CoverSub', parent=styles['Normal'],
        fontSize=18, leading=24, textColor=DARK, alignment=TA_CENTER,
    )))
    story.append(Spacer(1, 30))
    story.append(Paragraph("Versiunea 1.0 - Martie 2026", ParagraphStyle(
        'CoverDate', parent=styles['Normal'],
        fontSize=11, textColor=SLATE, alignment=TA_CENTER,
    )))
    story.append(Spacer(1, 60))

    # Table of contents
    story.append(Paragraph("Cuprins", styles['H2']))
    toc_data = [
        ["1.", "Dashboard", "Prezentare generala si actiuni principale"],
        ["2.", "Gantt", "Vizualizare temporala a planificarii"],
        ["3.", "Board Masini", "Vizualizare pe resurse (masini)"],
        ["4.", "Comenzi", "Lista comenzilor de productie"],
        ["5.", "Planificare", "Rezultatele algoritmului de planificare"],
        ["6.", "Stoc Materiale", "Situatia stocurilor si deficitelor"],
        ["7.", "Algoritmul de Planificare", "Descriere detaliata a logicii"],
    ]
    toc_table = Table(toc_data, colWidths=[25, 100, 310])
    toc_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TEXTCOLOR', (0, 0), (0, -1), BLUE),
        ('TEXTCOLOR', (1, 0), (1, -1), DARK),
        ('TEXTCOLOR', (2, 0), (2, -1), SLATE),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(toc_table)
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # 1. DASHBOARD
    # ═══════════════════════════════════════════════════════════════
    story.append(Paragraph("1. Dashboard", styles['H1']))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=12))

    story.append(Paragraph(
        "Dashboard-ul este ecranul principal al aplicatiei. Ofera o privire de ansamblu "
        "asupra intregii activitati de productie si permite executarea actiunilor principale.",
        styles['Body']))

    story.append(Paragraph("Actiuni disponibile", styles['H2']))

    story.append(Paragraph(
        "<b>Import Date Excel</b> - Incarca datele din fisierele Excel exportate din ERP "
        "(comenzi, operatii dispatch, operatii catalog, deficit/stoc, resurse si program resurse). "
        "Aceasta este prima actiune necesara dupa o actualizare a datelor din ERP.",
        styles['Bullet']))
    story.append(Paragraph(
        "<b>Ruleaza Planificarea</b> - Executa algoritmul de planificare automata. "
        "Analizeaza toate comenzile active si aloca operatiile pe resurse in functie de "
        "disponibilitate, materiale, BT si dependente de rank. Rezultatele sunt vizibile "
        "in tab-urile Gantt, Board Masini si Planificare.",
        styles['Bullet']))

    story.append(Paragraph("Carduri statistice", styles['H2']))
    stats_data = [
        [Ph("Card"), Ph("Descriere")],
        [P("Total Comenzi"), P("Numarul total de comenzi incarcate in sistem (inclusiv STOP)")],
        [P("Comenzi Active"), P("Comenzi cu status LIBER (pot fi planificate)")],
        [P("Comenzi STOP"), P("Comenzi blocate/suspendate (excluse din planificare)")],
        [P("Operatii Dispatch"), P("Total operatii din listele de dispatch (munca de executat)")],
        [P("Resurse"), P("Numarul de masini/oameni disponibili pentru planificare")],
    ]
    t = Table(stats_data, colWidths=[120, 345])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Sub carduri se afiseaza graficele Stadiu Prepress (distributia comenzilor pe stadii) "
        "si informatii despre ultima sesiune de planificare executata.",
        styles['Body']))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # 2. GANTT
    # ═══════════════════════════════════════════════════════════════
    story.append(Paragraph("2. Gantt", styles['H1']))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=12))

    story.append(Paragraph(
        "Tab-ul Gantt afiseaza o diagrama de tip Gantt cu toate operatiile planificate. "
        "Fiecare bara reprezinta o operatie alocata pe o resursa, cu durata si "
        "dependentele vizibile.",
        styles['Body']))

    story.append(Paragraph("Functionalitati", styles['H2']))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> <b>Filtru Centru de Lucru</b> - Selecteaza un centru de lucru "
        "(CL) pentru a vedea doar operatiile aferente (ex: FAL, SM, BINDER)",
        styles['Bullet']))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> <b>Cautare WO</b> - Cauta o comanda specifica dupa numarul WO",
        styles['Bullet']))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> <b>Vizualizare Day/Week/Month</b> - Schimba granularitatea axei temporale",
        styles['Bullet']))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> <b>Buton Today</b> - Navigheaza rapid la data curenta",
        styles['Bullet']))

    story.append(Paragraph("Navigare", styles['H2']))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> <b>Scroll vertical</b> - Deruleaza lista operatiilor",
        styles['Bullet']))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> <b>Scroll orizontal</b> - Navigheaza in timp (stanga = trecut, dreapta = viitor)",
        styles['Bullet']))

    story.append(Paragraph("Coduri culori", styles['H2']))
    color_data = [
        [Ph("Culoare"), Ph("Semnificatie")],
        [P("Albastru"), P("Operatie planificata (in termen)")],
        [P("Rosu"), P("Operatie intarziata (data end depasita)")],
        [P("Mov"), P("Operatie blocata/frozen")],
    ]
    t = Table(color_data, colWidths=[120, 345])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Sagetile intre bare arata dependentele (inlantuirea operatiilor). O operatie "
        "de rank superior (ex: ambalare) incepe doar dupa terminarea operatiei de rank "
        "inferior (ex: tipar).",
        styles['Body']))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # 3. BOARD MASINI
    # ═══════════════════════════════════════════════════════════════
    story.append(Paragraph("3. Board Masini", styles['H1']))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=12))

    story.append(Paragraph(
        "Board Masini ofera o vizualizare centrata pe resurse, inspirata de solutia "
        "Theurer.com. Fiecare rand reprezinta o masina/resursa, iar pe axa "
        "orizontala se vad orele din zi. Operatiile sunt afisate ca bare colorate "
        "pozitionate in timp pe fiecare masina.",
        styles['Body']))

    story.append(Paragraph("Functionalitati", styles['H2']))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> <b>Filtru Centru de Lucru</b> - Selecteaza un CL sau vizualizeaza "
        "toate centrele simultan",
        styles['Bullet']))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> <b>Buton Azi</b> - Navigheaza la ora curenta",
        styles['Bullet']))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> <b>Reincarca</b> - Actualizeaza datele de pe server",
        styles['Bullet']))

    story.append(Paragraph("Navigare", styles['H2']))
    nav_data = [
        [Ph("Actiune"), Ph("Efect")],
        [P("Scroll (rotita mouse)"), P("Navigheaza stanga/dreapta pe axa timpului")],
        [P("Ctrl + Scroll"), P("Zoom in/out (mareste/micsoreaza intervalul vizibil)")],
        [P("Drag (click + trage)"), P("Pan liber in orice directie")],
    ]
    t = Table(nav_data, colWidths=[140, 325])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Informatii afisate", styles['H2']))
    story.append(Paragraph(
        "Badge-urile din dreapta arata: numarul de masini vizibile, numarul total de "
        "operatii planificate, si numarul de operatii intarziate (cu data de sfarsit "
        "in trecut). Tooltip-ul afisat la hover pe o bara contine detalii: WO, operatie, "
        "client, durata, interval orar.",
        styles['Body']))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # 4. COMENZI
    # ═══════════════════════════════════════════════════════════════
    story.append(Paragraph("4. Comenzi", styles['H1']))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=12))

    story.append(Paragraph(
        "Tab-ul Comenzi afiseaza lista tuturor comenzilor de productie importate din ERP. "
        "Permite cautarea si filtrarea rapida.",
        styles['Body']))

    story.append(Paragraph("Carduri statistice live", styles['H2']))
    story.append(Paragraph(
        "In partea de sus se afiseaza 4 carduri care reflecta rezultatele cautarii/filtrarii curente:",
        styles['Body']))
    cards_data = [
        [Ph("Card"), Ph("Descriere"), Ph("Actiune la click")],
        [P("Total comenzi"), P("Numarul total de comenzi afisate"), P("-")],
        [P("06 - In productie"), P("Comenzi cu stadiu prepress 'In productie'"), P("Filtreaza dupa acest stadiu")],
        [P("LIBER"), P("Comenzi cu status activ"), P("Filtreaza dupa status LIBER")],
        [P("STOP"), P("Comenzi blocate"), P("Filtreaza dupa status STOP")],
    ]
    t = Table(cards_data, colWidths=[100, 200, 165])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        '<b>Nota:</b> Cardurile sunt interactive - un click pe un card filtreaza tabelul '
        'dupa criteriul respectiv. Al doilea click revine la vizualizarea completa. '
        'Cand se aplica un filtru sau o cautare, label-ul se schimba in "Rezultate filtrate".',
        styles['Note']))

    story.append(Paragraph("Cautare si filtrare", styles['H2']))
    story.append(Paragraph(
        "Campul de cautare permite gasirea comenzilor dupa: numar CP, numar CV, "
        "nume client, articol, sau referinta client. Dropdown-ul de status permite "
        "filtrarea dupa LIBER sau STOP.",
        styles['Body']))

    story.append(Paragraph(
        "Fiecare rand din tabel poate fi expandat (click pe sageata >) pentru a vedea "
        "operatiile dispatch asociate comenzii.",
        styles['Body']))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # 5. PLANIFICARE
    # ═══════════════════════════════════════════════════════════════
    story.append(Paragraph("5. Planificare", styles['H1']))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=12))

    story.append(Paragraph(
        "Tab-ul Planificare afiseaza rezultatele detaliate ale ultimei sesiuni de planificare. "
        "Fiecare operatie din dispatch apare cu statusul ei de planificare.",
        styles['Body']))

    story.append(Paragraph("Carduri statistice", styles['H2']))
    plan_cards = [
        [Ph("Card"), Ph("Culoare"), Ph("Descriere")],
        [P("Total afisate"), P("Gri"), P("Numarul de operatii vizibile dupa filtrare")],
        [P("Planificate"), P("Verde"), P("Operatii alocate pe o resursa, cu date start/end")],
        [P("Fara Material"), P("Rosu"), P("Operatii blocate - stoc insuficient pentru comanda")],
        [P("Fara BT"), P("Portocaliu"), P("Comanda nu are Bun de Tipar valid")],
        [P("Blocate Rank"), P("Galben"), P("Operatia asteapta finalizarea unei operatii anterioare")],
        [P("Fara Resursa"), P("Gri"), P("Nu exista resursa disponibila in centrul de lucru")],
    ]
    t = Table(plan_cards, colWidths=[100, 70, 295])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "Cardurile sunt interactive - click pe un card filtreaza tabelul dupa acel status. "
        "Cardul Planificate arata si numarul total de ore planificate.",
        styles['Note']))

    story.append(Paragraph("Filtre", styles['H2']))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> <b>Centru de lucru</b> - Filtreaza dupa CL (ex: FAL, SM, BINDER, etc.)",
        styles['Bullet']))
    story.append(Paragraph(
        "<bullet>&bull;</bullet> <b>Status</b> - Filtreaza dupa statusul de planificare",
        styles['Bullet']))

    story.append(Paragraph("Coloane tabel", styles['H2']))
    col_data = [
        [Ph("Coloana"), Ph("Descriere")],
        [P("WO"), P("Numarul Work Order (comanda de productie)")],
        [P("OP"), P("Codul operatiei din catalog")],
        [P("CL"), P("Centrul de lucru (tipul de masina/sectie)")],
        [P("Resursa"), P("Masina/persoana alocata (doar pentru Planificate)")],
        [P("Status"), P("Statusul operatiei (Planificat, Fara Material, etc.)")],
        [P("Start / End"), P("Datele de inceput si sfarsit planificate")],
        [P("Durata (h)"), P("Timpul ramas de executat in ore")],
        [P("Motiv"), P("Motivul pentru care operatia nu a putut fi planificata")],
    ]
    t = Table(col_data, colWidths=[90, 375])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t)
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # 6. STOC MATERIALE
    # ═══════════════════════════════════════════════════════════════
    story.append(Paragraph("6. Stoc Materiale", styles['H1']))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=12))

    story.append(Paragraph(
        "Tab-ul Stoc Materiale afiseaza situatia stocurilor de materii prime si materiale. "
        "Este esential pentru a intelege de ce anumite comenzi nu pot fi planificate.",
        styles['Body']))

    story.append(Paragraph("Carduri statistice", styles['H2']))
    stoc_cards = [
        [Ph("Card"), Ph("Descriere")],
        [P("Total articole"), P("Numarul total de articole de stoc afisate")],
        [P("Disponibil"), P("Articole cu stoc pozitiv (sold > rezervari)")],
        [P("Epuizat"), P("Articole cu sold zero (fara stoc disponibil)")],
        [P("Deficit"), P("Articole cu disponibil negativ (cerere > stoc existent)")],
    ]
    t = Table(stoc_cards, colWidths=[110, 355])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Calcul disponibil", styles['H2']))
    story.append(Paragraph(
        "Formula de calcul este: <b>Disponibil = Sold Actual + Total Rezervat</b>",
        styles['Body']))
    story.append(Paragraph(
        "Unde Total Rezervat este suma cantitatilor din rezervarile de tip B (comenzi de productie). "
        "Cantitatile sunt stocate cu semn negativ (consum), deci adunarea este corecta: "
        "sold + (-cantitate_rezervata) = sold - cantitate_rezervata = disponibil real.",
        styles['Body']))

    story.append(Paragraph(
        '<b>Important:</b> Articolele cu disponibil negativ (rosu in tabel) sunt cauza directa '
        'a operatiilor marcate "Fara Material" in tab-ul Planificare. Aprovizionarea acestor '
        'articole va debloca planificarea comenzilor respective.',
        styles['Note']))

    story.append(Paragraph("Filtrare", styles['H2']))
    story.append(Paragraph(
        "Cardurile Epuizat si Deficit sunt clickabile - un click filtreaza tabelul "
        "pentru a afisa doar articolele cu acel status. Campul de cautare permite "
        "gasirea rapida dupa codul articolului.",
        styles['Body']))
    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # 7. ALGORITMUL DE PLANIFICARE
    # ═══════════════════════════════════════════════════════════════
    story.append(Paragraph("7. Algoritmul de Planificare", styles['H1']))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=12))

    story.append(Paragraph(
        "Algoritmul de planificare automata este componenta centrala a aplicatiei. "
        "El decide ce operatii se pot executa, pe ce masini si cand, respectand "
        "constrangerile reale de productie.",
        styles['Body']))

    # --- 7.1 ---
    story.append(Paragraph("7.1 Ordinea de procesare a comenzilor", styles['H2']))
    story.append(Paragraph(
        "Comenzile sunt procesate in ordinea prioritatii. Aceasta ordine determina "
        "care comenzi primesc resurse primele:",
        styles['Body']))

    prio_data = [
        [Phd("Prioritate"), Phd("Criteriu"), Phd("Exemplu")],
        [Ps("1 (cea mai mare)"), Ps("Stadiu Prepress mai avansat"), Ps("06 - In productie > 05 - BT existent")],
        [Ps("2"), Ps("Data livrare mai apropiata"), Ps("Comanda cu livrare pe 25.03 > livrare pe 30.03")],
        [Ps("3"), Ps("Comenzile STOP sunt excluse"), Ps("Nu se planifica deloc")],
    ]
    t = Table(prio_data, colWidths=[100, 170, 195])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # --- 7.2 ---
    story.append(Paragraph("7.2 Verificarile pentru fiecare operatie", styles['H2']))
    story.append(Paragraph(
        "Pentru fiecare comanda, operatiile sunt procesate in ordinea rank-ului "
        "(de la prima operatie - ex: tipar - la ultima - ex: ambalare). "
        "Fiecare operatie trece prin 4 verificari, in aceasta ordine:",
        styles['Body']))

    story.append(Paragraph("Verificare 1: Bun de Tipar (BT)", styles['H3']))
    story.append(Paragraph(
        "Se verifica daca comanda are un Bun de Tipar valid. BT-ul este documentul "
        "care autorizeaza inceperea tiparului. Daca niciun camp BT (BT1-BT4) nu este "
        "completat sau contine data invalida (1911-11-11), TOATE operatiile comenzii "
        'sunt marcate <font color="#ea580c"><b>Fara BT</b></font>.',
        styles['Body']))

    story.append(Paragraph("Verificare 2: Dependente de Rank", styles['H3']))
    story.append(Paragraph(
        "Fiecare operatie are un rank (rang) care defineste ordinea de executie in cadrul "
        "unei comenzi. Exemplu: tipar (rank 1) trebuie terminat inainte de faltuit (rank 2), "
        "iar ambalarea (rank 3) vine dupa faltuit.",
        styles['Body']))

    rank_rules = [
        [Phd("Starea operatiei precedente"), Phd("Efect asupra operatiei curente")],
        [Ps("Completata (remaining = 0)"), Ps("Nicio restrictie - se poate planifica imediat")],
        [Ps("Planificata (alocata pe masina)"), Ps("Se poate planifica, dar va incepe dupa data de "
         "sfarsit a operatiei precedente + 1 zi")],
        [Ps("Deschisa (neplanificata)"), Ps("Blocata - nu se poate planifica pana cand operatia "
         "precedenta nu este macar planificata")],
    ]
    t = Table(rank_rules, colWidths=[160, 305])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        '<b>Nota:</b> Cand o comanda are mai multe operatii la acelasi rank (ex: doua operatii '
        'rank 2 pe centre de lucru diferite), algoritmul pastreaza cel mai restrictiv status. '
        'Daca cel putin o operatie la rank 2 este "deschisa", toate operatiile de rank 3+ sunt '
        'blocate. Daca cel putin una este "planificata", rank 3+ asteapta cea mai tarzie data '
        'de sfarsit dintre toate operatiile de rank 2.',
        styles['Note']))

    story.append(Paragraph("Verificare 3: Disponibilitate Materiale", styles['H3']))
    story.append(Paragraph(
        "Se verifica daca materialele necesare comenzii sunt disponibile in stoc. "
        "Verificarea se face la nivel de comanda (WO), nu la nivel de operatie.",
        styles['Body']))
    story.append(Paragraph(
        "Algoritmul simuleaza un consum secvential: pe masura ce comenzile cu prioritate "
        "mai mare sunt planificate, ele \"consuma\" din stocul disponibil. Comenzile cu "
        "prioritate mai mica pot gasi stocul epuizat chiar daca la nivel global pare "
        'suficient. Acestea sunt marcate <font color="#dc2626"><b>Fara Material</b></font>.',
        styles['Body']))

    story.append(Paragraph("Verificare 4: Alocare pe Resursa", styles['H3']))
    story.append(Paragraph(
        "Daca toate verificarile anterioare sunt trecute, algoritmul cauta o resursa "
        "(masina/om) disponibila in centrul de lucru corespunzator operatiei.",
        styles['Body']))
    story.append(Paragraph(
        "Se cauta prima resursa care are ore disponibile incepand de la <b>earliest_start</b> "
        "(data cea mai devreme permisa de dependentele de rank sau data de azi). "
        "Operatia poate fi distribuita pe mai multe zile daca nu incape intr-o singura zi.",
        styles['Body']))

    alloc_example = [
        [Phd("Pas"), Phd("Actiune")],
        [Ps("1"), Ps("Se calculeaza durata ramasa: P_Setup + P_Runtime - R_Runtime")],
        [Ps("2"), Ps("Se cauta resurse din CL-ul operatiei care suporta codul operatiei")],
        [Ps("3"), Ps("Pentru fiecare resursa, se cauta prima zi cu ore disponibile >= earliest_start")],
        [Ps("4"), Ps("Se aloca orele: daca ziua are suficient, se aloca totul; daca nu, "
         "se aloca partial si se continua pe ziua urmatoare")],
        [Ps("5"), Ps("Se scad orele alocate din capacitatea resursei (nu se mai pot folosi "
         "de alte operatii)")],
    ]
    t = Table(alloc_example, colWidths=[30, 435])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))
    story.append(PageBreak())

    # --- 7.3 ---
    story.append(Paragraph("7.3 Schema decizionala", styles['H2']))
    story.append(Paragraph(
        "Diagrama de mai jos rezuma fluxul de decizie pentru fiecare operatie:",
        styles['Body']))

    flow_green = ParagraphStyle('FlowGreen', parent=cell_style_sm, textColor=GREEN, fontName='Helvetica-Bold')
    flow_orange = ParagraphStyle('FlowOrange', parent=cell_style_sm, textColor=ORANGE, fontName='Helvetica-Bold')
    flow_amber = ParagraphStyle('FlowAmber', parent=cell_style_sm, textColor=AMBER, fontName='Helvetica-Bold')
    flow_red = ParagraphStyle('FlowRed', parent=cell_style_sm, textColor=RED, fontName='Helvetica-Bold')
    flow_slate = ParagraphStyle('FlowSlate', parent=cell_style_sm, textColor=SLATE, fontName='Helvetica-Bold')

    flow_data = [
        [Phd(""), Phd("Decizie / Actiune"), Phd("Rezultat")],
        [Ps("1"), Ps("Operatia este deja terminata? (remaining = 0)"), P("DA: Skip (completata)", flow_green)],
        [Ps("2"), Ps("Comanda are BT valid?"), P("NU: Status = Fara BT", flow_orange)],
        [Ps("3"), Ps("Toate operatiile de rank inferior<br/>sunt completate sau planificate?"),
         P("NU: Status = Blocat Rank", flow_amber)],
        [Ps("4"), Ps("Materialele comenzii sunt disponibile in stoc?"),
         P("NU: Status = Fara Material", flow_red)],
        [Ps("5"), Ps("Exista resursa disponibila in CL-ul operatiei?"),
         P("NU: Status = Fara Resursa", flow_slate)],
        [Ps("6"), Ps("Aloca pe prima resursa cu slot disponibil"),
         P("DA: Status = Planificat", flow_green)],
    ]
    t = Table(flow_data, colWidths=[25, 230, 210])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9.5),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

    # --- 7.4 ---
    story.append(Paragraph("7.4 Exemplu concret", styles['H2']))
    story.append(Paragraph(
        "Comanda WO 8300001879 (client: exemplu) cu 4 operatii:",
        styles['Body']))

    example_data = [
        [Phd("Op"), Phd("CL"), Phd("Rank"), Phd("Durata"), Phd("Logica de alocare")],
        [Ps("732"), Ps("MGN"), Ps("1"), Ps("0.2h"),
         Ps("Rank 1 → prima operatie. Nicio dependenta. Alocat pe<br/>'Linie magneziu' (24.03). Status: Planificat.")],
        [Ps("715"), Ps("FAL"), Ps("3"), Ps("1.1h"),
         Ps("Rank 3 → asteapta rank 1 (end=24.03). earliest_start=25.03.<br/>Alocat pe 'Stahl 1' (25.03). Status: Planificat.")],
        [Ps("880"), Ps("OPMP"), Ps("5"), Ps("1.1h"),
         Ps("Rank 5 → asteapta rank 3 (end=25.03). earliest_start=26.03.<br/>Alocat pe 'Persoana 1 OPMAN' (26.03). Status: Planificat.")],
        [Ps("777"), Ps("POL"), Ps("4"), Ps("1.2h"),
         Ps("Rank 4 → asteapta rank 3 (end=25.03). earliest_start=26.03.<br/>Alocat pe resursa POL (26.03). Status: Planificat.")],
    ]
    t = Table(example_data, colWidths=[28, 38, 32, 38, 329])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

    # --- 7.5 ---
    story.append(Paragraph("7.5 Capacitatea resurselor", styles['H2']))
    story.append(Paragraph(
        "Fiecare resursa are un program definit pe zile cu numarul de ore disponibile "
        "si schimburile active. Exemplu: o masina cu schimburi '6-14;14-22' are "
        "16 ore/zi disponibile. Algoritmul respecta strict aceste ore - nu programeaza "
        "mai multe ore decat sunt disponibile pe o resursa intr-o zi.",
        styles['Body']))

    story.append(Paragraph(
        "Daca o operatie necesita mai multe ore decat are o zi, ea se distribuie pe "
        "mai multe zile consecutive (split). Exemplu: o operatie de 37h pe o resursa "
        "cu 16h/zi se va intinde pe 3 zile (16h + 16h + 5h).",
        styles['Body']))
    story.append(Spacer(1, 20))

    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=15))
    story.append(Paragraph(
        "Generat automat - Arta Grafica Planificare Productie v1.0",
        ParagraphStyle('Footer', parent=styles['Normal'],
                       fontSize=9, textColor=SLATE, alignment=TA_CENTER)))

    # Build
    doc.build(story)
    print(f"PDF generat: {OUTPUT}")


if __name__ == "__main__":
    build_pdf()
