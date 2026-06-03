# Arhitectura Arta Grafica — Planificare Producție

## 1. Vedere de ansamblu (Mind Map)

```mermaid
mindmap
  root((Arta Grafica))
    Frontend
      React + TypeScript
      TailwindCSS
      Cloudflare Pages
      Componente UI
        Dashboard + AI
        Comenzi
        Planificare
        Gantt
        Board Mașini
        Stoc
        Setări
    Backend
      FastAPI · Python 3.11
      Fly.io · Londra
      Module
        main.py · API routes
        planner.py · Algoritm
        importer.py · Import Excel
        models.py · Schema DB
    Date
      SQLite · /data/planning.db
      Volum persistent 3 GB
      Tabele principale
        comenzi
        dispatch
        deficite
        resurse
        program_resurse
        planificare_rezultate
        setari
    Integrări
      Anthropic Claude API
        Streaming SSE
        Răspunsuri AI
      Excel · Import date
        Stari comenzi
        Dispatch List
        Operatii WO
        Lista Deficite
        Resurse
    Securitate
      Token SHA-256
      Auth middleware
      HTTPS forțat
```

---

## 2. Flux de date

```mermaid
flowchart LR
    User(["👤 Utilizator"])
    CF["Cloudflare Pages\narta-grafica.pages.dev"]
    FLY["Fly.io Backend\narta-grafica.fly.dev"]
    DB[("SQLite\n/data/planning.db")]
    AI["Anthropic\nClaude API"]
    XLS["Fișiere Excel\ndin ERP"]

    User -->|HTTPS| CF
    CF -->|API calls + JWT| FLY
    FLY <-->|SQLAlchemy ORM| DB
    FLY -->|POST + SSE stream| AI
    AI -->|text stream| FLY
    XLS -->|Upload /api/import| FLY
```

---

## 3. Algoritmul de planificare

```mermaid
flowchart TD
    START([Start planificare]) --> SORT

    SORT["1️⃣ Sortare comenzi\nStadiu Prepress ↓\nData livrare ↑\nCu material → primele"]

    SORT --> FILTER["2️⃣ Exclude STOP"]

    FILTER --> LOOP["Pentru fiecare comandă\n― operații sortate după Rank ―"]

    LOOP --> BT{"3️⃣ BT valid?\nsau Stadiu ≥ 50?"}

    BT -->|Nu + are DataLimitaBT| PREV_BT["Previzionat\nfara BT\nstart = DataLimitaBT"]
    BT -->|Nu + fara DataLimitaBT| NO_BT["❌ Blocat\nfara BT"]

    BT -->|Da| MAT{"4️⃣ Material\ndisponibil?\ncantitate/tiraj ≤ prag → ignorat"}

    MAT -->|Nu + aprovizionare| PREV_MAT["Previzionat\nfara material\nstart = data aprovizionare"]
    MAT -->|Nu + semifabricat intern| PREV_SEMI["Previzionat\nfara semifabricat\nstart = end WO producător"]
    MAT -->|Nu + fara perspectivă| NO_MAT["❌ Blocat\nfara material"]

    MAT -->|Da| RANK{"5️⃣ Rank OK?\npredecesori\nplanificați/finalizați?"}

    RANK -->|Nu| NO_RANK["❌ Blocat Rank"]

    RANK -->|Da| RES{"6️⃣ Resursă\ndisponibilă\nîn CL?"}

    RES -->|Nu| NO_RES["❌ Fara Resursă"]

    RES -->|Da| ALLOC["7️⃣ Alocare slot\nresursa cu cel mai\ndevreme slot liber\nLoad balancing"]

    ALLOC --> TIME["8️⃣ Calcul timp\nP_Setup + P_Runtime\n− R_Runtime"]

    TIME --> SAVED["✅ Planificat\ndata_start / data_end\nstocată în DB"]

    NO_BT --> NEXT
    NO_MAT --> NEXT
    NO_RANK --> NEXT
    NO_RES --> NEXT
    PREV_BT --> NEXT
    PREV_MAT --> NEXT
    PREV_SEMI --> NEXT
    SAVED --> NEXT

    NEXT{Mai sunt\noperații?}
    NEXT -->|Da| LOOP
    NEXT -->|Nu| END([Sesiune salvată\nîn DB])

    style SAVED fill:#16a34a,color:#fff
    style NO_BT fill:#ea580c,color:#fff
    style NO_MAT fill:#ea580c,color:#fff
    style NO_RANK fill:#f59e0b,color:#fff
    style NO_RES fill:#64748b,color:#fff
    style PREV_BT fill:#2563eb,color:#fff
    style PREV_MAT fill:#2563eb,color:#fff
    style PREV_SEMI fill:#7c3aed,color:#fff
```

---

## 4. Deployment

```mermaid
flowchart TB
    subgraph DEV["💻 Development (local)"]
        VITE["Vite dev server :5173\n→ proxy /api → :8000"]
        UVICORN_DEV["uvicorn :8000\n--reload"]
        SQLITE_DEV[("SQLite local\ndata/planning.db")]
    end

    subgraph PROD["☁️ Production"]
        subgraph CF_PAGES["Cloudflare Pages (CDN global)"]
            STATIC["Static bundle\nindex.html + JS + CSS"]
        end
        subgraph FLYIO["Fly.io · London (lhr)"]
            DOCKER["Docker container\nPython 3.11 + Node"]
            UVICORN_PROD["uvicorn :8080\n--workers 2"]
            SQLITE_PROD[("SQLite\n/data/planning.db\nVolum 3 GB")]
        end
    end

    GIT["GitHub\naria-grafica/main"] -->|auto-build| CF_PAGES
    GIT -->|fly deploy| FLYIO
    UVICORN_PROD <-->|SQLAlchemy| SQLITE_PROD
    DOCKER --> UVICORN_PROD
```

---

## 5. Statusuri operații

| Status | Culoare | Semnificație |
|---|---|---|
| **Planificat** | 🟢 Verde | Slot alocat, BT + material OK |
| **Previzionat (fara BT)** | 🔵 Albastru | BT lipsă dar are DataLimitaBT |
| **Previzionat (fara material)** | 🔵 Albastru | Material vine prin aprovizionare |
| **Previzionat (semifabricat)** | 🔵 Albastru | Material produs de alt WO planificat |
| **Blocat (fara BT)** | 🟠 Portocaliu | Fara BT, fara DataLimitaBT |
| **Blocat (fara material)** | 🔴 Roșu | Stoc insuficient, fara aprovizionare |
| **Blocat (fara BT + material)** | 🔴 Roșu | Ambele lipsesc simultan |
| **Blocat Rank** | 🟡 Galben | Predecesori neplanificați |
| **Frozen — posibil** | 🟣 Violet | Înghețat, condițiile curente OK |
| **Frozen — imposibil** | 🟠 Portocaliu | Înghețat, BT sau material lipsesc acum |
