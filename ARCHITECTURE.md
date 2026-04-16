# 404 Found Us — Architecture

## System Overview

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#D6EAF8', 'primaryTextColor': '#1a1a2e', 'primaryBorderColor': '#4A90D9', 'lineColor': '#4A90D9', 'secondaryColor': '#E8F4FD', 'tertiaryColor': '#F5FAFF', 'fontFamily': 'Segoe UI, sans-serif', 'fontSize': '16px' }, 'flowchart': { 'nodeSpacing': 40, 'rankSpacing': 50, 'padding': 16 }}}%%
graph TB
    USER(("Browser<br/>(User)"))

    USER -->|http| NG

    NG["CENTRAL PLATFORM GATEWAY<br/>Nginx :80<br/>Reverse Proxy · nginx:alpine"]

    NG -->|"/sales/*"| FE
    NG -->|"/api/*"| BE
    NG -->|"/ml/*"| MLS
    NG -->|"/merchant/*"| MFE

    subgraph Services["  "]
        direction LR
        FE["sales-frontend :3000<br/><b>INTERNAL SALES PORTAL</b><br/>built with React CRA"]
        BE["backend :8000<br/><b>COST CALCULATOR</b><br/>calculates processing costs<br/>powered by FastAPI<br/>(TransactionCostCalc)"]
        MLS["ml-service :8001<br/><b>PREDICTION ENGINE</b><br/>FastAPI · KNN Rate Quote<br/>Cost Forecast · TPV Forecast<br/>Profit Forecast · Rate Optimisation<br/>TPV Prediction · Monte Carlo"]
        MFE["merchant-frontend :3001<br/><b>MERCHANT SELF-SERVICE</b><br/>built with Vite + React + TS"]
    end

    BE -->|httpx| MLS

    BE -->|Uses rules| CS
    BE -->|Reads| DB
    MLS -->|Reads/Writes data<br/>SQLAlchemy| DB

    subgraph Data["  "]
        direction LR
        CS["COST STRUCTURE JSONs<br/>Visa & Mastercard<br/>fee rules and rates"]
        DB[("Database<br/>(SQLAlchemy)")]
    end

    subgraph Tables["  "]
        direction LR
        DB1[("transaction records<br/>(knn_transactions)")]
        DB2[("cost classifications<br/>(knn_cost_type_ref)")]
    end

    DB --- DB1
    DB --- DB2

    style USER fill:#ffffff,stroke:#1B3A5C,stroke-width:4px,color:#1a1a2e
    style NG fill:#1B3A5C,stroke:#1B3A5C,stroke-width:3px,color:#ffffff
    style Services fill:#ffffff,stroke:#ffffff,stroke-width:0px
    style Data fill:#ffffff,stroke:#ffffff,stroke-width:0px
    style Tables fill:#ffffff,stroke:#ffffff,stroke-width:0px

    style FE fill:#D6EAF8,stroke:#1B3A5C,stroke-width:3px,color:#1a1a2e
    style BE fill:#D6EAF8,stroke:#1B3A5C,stroke-width:3px,color:#1a1a2e
    style MLS fill:#4A90D9,stroke:#1B3A5C,stroke-width:3px,color:#ffffff
    style MFE fill:#D6EAF8,stroke:#1B3A5C,stroke-width:3px,color:#1a1a2e

    style CS fill:#E8F4FD,stroke:#4A90D9,stroke-width:3px,color:#1a1a2e
    style DB fill:#1B3A5C,stroke:#1B3A5C,stroke-width:3px,color:#ffffff
    style DB1 fill:#1B3A5C,stroke:#1B3A5C,stroke-width:3px,color:#ffffff
    style DB2 fill:#1B3A5C,stroke:#1B3A5C,stroke-width:3px,color:#ffffff

    linkStyle default stroke:#4A90D9,stroke-width:3px
```

## Detailed Service Architecture

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#D6EAF8', 'primaryTextColor': '#1a1a2e', 'primaryBorderColor': '#4A90D9', 'lineColor': '#4A90D9', 'fontFamily': 'Segoe UI, sans-serif' }}}%%
graph LR
    subgraph nginx["Nginx :80"]
        direction TB
        R1["/ → 301 /sales/"]
        R2["/sales/* → frontend:3000"]
        R3["/merchant/* → merchant-frontend:3001"]
        R4["/api/* → backend:8000"]
        R5["/ml/* → ml-service:8001"]
    end

    style nginx fill:#1B3A5C,stroke:#1B3A5C,stroke-width:2px,color:#ffffff
    style R1 fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style R2 fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style R3 fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style R4 fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style R5 fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
```

## Backend API Endpoints

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#D6EAF8', 'primaryTextColor': '#1a1a2e', 'primaryBorderColor': '#4A90D9', 'lineColor': '#4A90D9', 'fontFamily': 'Segoe UI, sans-serif' }}}%%
graph LR
    subgraph backend["Backend /api/v1"]
        direction TB

        subgraph calc["Calculations"]
            TC["POST /calculations/transaction-costs<br/>Primary: CSV upload → enriched CSV + metrics"]
            MF["POST /calculations/merchant-fee<br/>Calculate current interchange rates"]
            DM["POST /calculations/desired-margin<br/>Rate needed for target margin"]
            DMD["POST /calculations/desired-margin-details<br/>Aggregator: calls 4 ML endpoints"]
        end

        subgraph txn["Transactions"]
            TU["POST /transactions/upload<br/>CSV/Excel validation & storage"]
            TL["GET /transactions<br/>List (paginated)"]
            TG["GET /transactions/:id"]
        end

        subgraph merch["Merchants"]
            ML2["GET /merchants"]
            MG["GET /merchants/:id"]
            MC["POST /merchants"]
        end

        subgraph mcc["MCC Codes"]
            MA["GET /mcc-codes"]
            MS["GET /mcc-codes/search"]
            MCC2["GET /mcc-codes/:code"]
        end

        subgraph quote["Merchant Quote"]
            MQ["POST /merchant-quote<br/>Generate quote + ML insights"]
        end
    end

    style backend fill:#E8F4FD,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style calc fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style txn fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style merch fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style mcc fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style quote fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style TC fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style MF fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style DM fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style DMD fill:#ffffff,stroke:#1B3A5C,stroke-width:2px,color:#1a1a2e
    style TU fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style TL fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style TG fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style ML2 fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style MG fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style MC fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style MA fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style MS fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style MCC2 fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style MQ fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
```

## ML Service Modules & Endpoints

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#D6EAF8', 'primaryTextColor': '#1a1a2e', 'primaryBorderColor': '#4A90D9', 'lineColor': '#4A90D9', 'fontFamily': 'Segoe UI, sans-serif' }}}%%
graph TB
    subgraph ml["ML Service /ml"]
        direction TB

        ORCH["POST /ml/process<br/>Orchestrator: runs all 3 engines"]

        subgraph engines["Core Engines (called by /ml/process)"]
            RO["rate_optimisation/<br/>Rate Optimisation Engine"]
            TP["tpv_prediction/<br/>TPV Prediction Engine"]
            KNN["knn_rate_quote/<br/>KNN Rate Quote Engine"]
        end

        subgraph forecast["Forecast Services"]
            CF["cost_forecast/<br/>POST /ml/GetCostForecast<br/>M9 v2 monthly cost forecast"]
            VF["volume_forecast/<br/>POST /ml/GetVolumeForecast<br/>SARIMAX weekly volume"]
            PF["profit_forecast/<br/>POST /ml/GetProfitForecast<br/>Monte Carlo simulation"]
            TF["tpv_forecast/<br/>POST /ml/GetTPVForecast<br/>Conformal TPV forecast"]
        end

        subgraph knn_endpoints["KNN Endpoints"]
            GQ["POST /ml/getQuote"]
            GCM["POST /ml/getCompositeMerchant"]
        end

        subgraph health["Health"]
            HH["GET /ml/cost-forecast/health"]
        end

        ORCH --> RO
        ORCH --> TP
        ORCH --> KNN
    end

    subgraph artifacts["Trained Model Artifacts"]
        M9["artifacts/m9/<br/>└─ 5411/{1,3,6}/<br/>&nbsp;&nbsp;&nbsp;├─ models.pkl<br/>&nbsp;&nbsp;&nbsp;├─ scaler.pkl<br/>&nbsp;&nbsp;&nbsp;├─ cal_residuals.pkl<br/>&nbsp;&nbsp;&nbsp;├─ risk_models.pkl<br/>&nbsp;&nbsp;&nbsp;└─ config_snapshot.json"]
        TPV["artifacts/tpv/<br/>├─ 4121/<br/>├─ 5411/<br/>├─ 5499/<br/>└─ 5812/"]
    end

    CF -.->|loads| M9
    TF -.->|loads| TPV

    style ml fill:#E8F4FD,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style engines fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style forecast fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style knn_endpoints fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style health fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style artifacts fill:#1B3A5C,stroke:#1B3A5C,stroke-width:2px,color:#ffffff

    style ORCH fill:#4A90D9,stroke:#1B3A5C,stroke-width:2px,color:#ffffff
    style RO fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style TP fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style KNN fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style CF fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style VF fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style PF fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style TF fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style GQ fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style GCM fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style HH fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style M9 fill:#4A90D9,stroke:#1B3A5C,stroke-width:2px,color:#ffffff
    style TPV fill:#4A90D9,stroke:#1B3A5C,stroke-width:2px,color:#ffffff
```

## Primary Data Flow — Transaction Cost Calculation

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'actorBkg': '#1B3A5C', 'actorTextColor': '#ffffff', 'actorBorder': '#1B3A5C', 'activationBorderColor': '#4A90D9', 'activationBkgColor': '#D6EAF8', 'sequenceNumberColor': '#ffffff', 'signalColor': '#4A90D9', 'signalTextColor': '#1a1a2e', 'labelBoxBkgColor': '#4A90D9', 'labelBoxBorderColor': '#1B3A5C', 'labelTextColor': '#ffffff', 'noteBkgColor': '#E8F4FD', 'noteBorderColor': '#4A90D9', 'noteTextColor': '#1a1a2e', 'loopTextColor': '#1B3A5C', 'fontFamily': 'Segoe UI, sans-serif' }}}%%
sequenceDiagram
    actor User
    participant FE as Sales Frontend
    participant NG as Nginx :80
    participant BE as Backend :8000
    participant ML as ML Service :8001
    participant DB as PostgreSQL

    User->>FE: Upload CSV + select MCC
    FE->>NG: POST /api/v1/calculations/transaction-costs?mcc=5411
    NG->>BE: proxy → backend:8000

    BE->>BE: Parse CSV, calculate card + network costs
    BE->>DB: Store CalculationResult

    par Streaming Response
        BE-->>FE: StreamingResponse (enriched CSV)<br/>Headers: X-Total-Cost, X-Effective-Rate,<br/>X-Slope, X-Cost-Variance, etc.
        FE-->>User: Display results in ResultsPanel
    and Background Task
        BE->>ML: POST /ml/process<br/>(enriched CSV + metrics)
        ML->>ML: 1. Rate Optimisation Engine
        ML->>ML: 2. TPV Prediction Engine
        ML->>ML: 3. KNN Rate Quote Engine
        ML->>DB: Persist ML results
    end
```

## Merchant Quotation Flow

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'actorBkg': '#1B3A5C', 'actorTextColor': '#ffffff', 'actorBorder': '#1B3A5C', 'activationBorderColor': '#4A90D9', 'activationBkgColor': '#D6EAF8', 'signalColor': '#4A90D9', 'signalTextColor': '#1a1a2e', 'labelBoxBkgColor': '#4A90D9', 'labelBoxBorderColor': '#1B3A5C', 'labelTextColor': '#ffffff', 'noteBkgColor': '#E8F4FD', 'noteBorderColor': '#4A90D9', 'noteTextColor': '#1a1a2e', 'loopTextColor': '#1B3A5C', 'fontFamily': 'Segoe UI, sans-serif' }}}%%
sequenceDiagram
    actor User
    participant MFE as Merchant Frontend
    participant NG as Nginx :80
    participant BE as Backend :8000
    participant ML as ML Service :8001

    User->>MFE: Fill quotation form
    MFE->>NG: POST /api/v1/merchant-quote
    NG->>BE: proxy → backend:8000

    BE->>ML: POST /ml/getCompositeMerchant
    ML-->>BE: composite merchant profile

    BE->>ML: POST /ml/GetTPVForecast
    ML-->>BE: conformal monthly TPV prediction

    BE->>ML: POST /ml/GetCostForecast
    ML-->>BE: 3-month cost forecast (M9 v2)

    BE->>ML: POST /ml/GetProfitForecast
    ML-->>BE: Monte Carlo profit simulation

    BE-->>MFE: QuoteResult (rates, charges, ml_insights)
    MFE-->>User: Display quotation

    Note over MFE: Falls back to placeholder quote<br/>if backend/ML errors
```

## Rates Quotation Tool — Data Flow

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#D6EAF8', 'primaryTextColor': '#1a1a2e', 'primaryBorderColor': '#4A90D9', 'lineColor': '#4A90D9', 'fontFamily': 'Segoe UI, sans-serif' }, 'flowchart': { 'nodeSpacing': 20, 'rankSpacing': 30, 'padding': 10 }}}%%
flowchart TB
    U["User enters:<br/>MCC · Transactions CSV<br/>Desired Margin (bps) · [Current Rate] · [Fixed Fee]"]
    FE["DesiredMarginCalculator.jsx"]
    EP["POST /api/v1/calculations/desired-margin-details"]
    COST["Backend: Calculate interchange<br/>& network costs from transactions"]

    subgraph ML["ML Pipeline (4 sequential calls)"]
        direction TB
        KNN["① /ml/getCompositeMerchant<br/>KNN → 5 nearest merchants"]
        TPV["② /ml/GetTPVForecast<br/>Conformal monthly TPV prediction"]
        M9["③ /ml/GetCostForecast<br/>M9 v2 → 3-month cost %"]
        MC["④ /ml/GetProfitForecast<br/>Monte Carlo simulation<br/>(uses cost + TPV + fee rate + fixed fee)"]
        KNN --> TPV --> M9 --> MC
    end

    ASSEMBLE["Backend assembles:<br/>Recommended rate · Profitability curve<br/>Cost & volume forecasts · Estimated profit range"]
    RES["DesiredMarginResults.jsx<br/>Charts: Cost Forecast · Volume Trend · Probability Curve"]

    U --> FE --> EP --> COST --> ML --> ASSEMBLE --> RES

    style U fill:#ffffff,stroke:#1B3A5C,stroke-width:2px,color:#1a1a2e
    style FE fill:#D6EAF8,stroke:#1B3A5C,stroke-width:2px,color:#1a1a2e
    style EP fill:#1B3A5C,stroke:#1B3A5C,stroke-width:2px,color:#ffffff
    style COST fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style ML fill:#E8F4FD,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style KNN fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style TPV fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style M9 fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style MC fill:#4A90D9,stroke:#1B3A5C,stroke-width:2px,color:#ffffff
    style ASSEMBLE fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style RES fill:#D6EAF8,stroke:#1B3A5C,stroke-width:2px,color:#1a1a2e
```

## Profitability Calculator — Data Flow

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#D6EAF8', 'primaryTextColor': '#1a1a2e', 'primaryBorderColor': '#4A90D9', 'lineColor': '#4A90D9', 'fontFamily': 'Segoe UI, sans-serif' }, 'flowchart': { 'nodeSpacing': 20, 'rankSpacing': 30, 'padding': 10 }}}%%
flowchart TB
    U["User enters:<br/>MCC · Transactions CSV<br/>[Current Rate] · [Fixed Fee]<br/>(desired margin hardcoded 1.5%)"]
    FE["EnhancedMerchantFeeCalculator.jsx"]
    EP["POST /api/v1/calculations/desired-margin-details"]
    COST["Backend: Calculate interchange<br/>& network costs from transactions"]

    subgraph ML["ML Pipeline (same 4 calls)"]
        direction TB
        KNN["① /ml/getCompositeMerchant<br/>KNN → 5 nearest merchants"]
        TPV["② /ml/GetTPVForecast<br/>Conformal monthly TPV prediction"]
        M9["③ /ml/GetCostForecast<br/>M9 v2 → 3-month cost %"]
        MC["④ /ml/GetProfitForecast<br/>Monte Carlo simulation<br/>(uses cost + TPV + fee rate + fixed fee)"]
        KNN --> TPV --> M9 --> MC
    end

    ASSEMBLE["Backend assembles:<br/>Cost & volume forecasts · Profitability curve<br/>Estimated profit range · Key metrics"]
    RES["ResultsPanel.jsx<br/>Charts: Cost Forecast · Volume Trend · Probability Curve<br/>+ Processing Volume · Fee Revenue"]

    U --> FE --> EP --> COST --> ML --> ASSEMBLE --> RES

    style U fill:#ffffff,stroke:#1B3A5C,stroke-width:2px,color:#1a1a2e
    style FE fill:#D6EAF8,stroke:#1B3A5C,stroke-width:2px,color:#1a1a2e
    style EP fill:#1B3A5C,stroke:#1B3A5C,stroke-width:2px,color:#ffffff
    style COST fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style ML fill:#E8F4FD,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style KNN fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style TPV fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style M9 fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style MC fill:#4A90D9,stroke:#1B3A5C,stroke-width:2px,color:#ffffff
    style ASSEMBLE fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style RES fill:#D6EAF8,stroke:#1B3A5C,stroke-width:2px,color:#1a1a2e
```

## Database Schema

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#D6EAF8', 'primaryTextColor': '#1a1a2e', 'primaryBorderColor': '#4A90D9', 'lineColor': '#4A90D9', 'entityBkg': '#ffffff', 'entityBorderColor': '#4A90D9', 'fontFamily': 'Segoe UI, sans-serif' }}}%%
erDiagram
    transactions {
        int id PK
        string transaction_id UK
        date transaction_date
        string merchant_id FK
        float amount
        string transaction_type
        string card_type
        string batch_id FK
        datetime created_at
        datetime updated_at
    }

    merchants {
        int id PK
        string merchant_id UK
        string merchant_name
        int mcc
        string industry
        float annual_volume
        float average_ticket
        float current_rate
        float fixed_fee
        datetime created_at
        datetime updated_at
    }

    calculation_results {
        int id PK
        string calculation_type
        string merchant_id
        int mcc
        int transaction_count
        float total_volume
        float total_fees
        float effective_rate
        float applied_rate
        float desired_margin
        float recommended_rate
        datetime created_at
    }

    upload_batches {
        int id PK
        string batch_id UK
        string filename
        string file_type
        string merchant_id
        int record_count
        string status
        int error_count
        datetime created_at
        datetime completed_at
    }

    knn_transactions {
        int id PK
        string transaction_id
        string merchant_id
        int mcc
        string card_brand
        string card_type
        date date
        float amount
        float proc_cost
        string cost_type_id
    }

    knn_cost_type_ref {
        int id PK
        string cost_type_id
    }

    merchants ||--o{ transactions : "has"
    upload_batches ||--o{ transactions : "contains"
    merchants ||--o{ calculation_results : "generates"
    knn_cost_type_ref ||--o{ knn_transactions : "classifies"
```

## Docker Compose Topology

```mermaid
graph TB
    subgraph docker["Docker Compose Network: ml-network"]
        subgraph proxy["Reverse Proxy"]
            nginx["nginx:alpine<br/>:80 → host :80"]
        end

        subgraph apps["Application Layer"]
            frontend["frontend<br/>React CRA :3000"]
            merchant["merchant-frontend<br/>Vite+React :3001"]
            backend["backend<br/>FastAPI :8000"]
            mlservice["ml-service<br/>FastAPI :8001"]
        end

        subgraph data["Data Layer"]
            postgres[("PostgreSQL 16 :5432")]
            vol_pg[("postgres_data<br/>named volume")]
        end

        subgraph volumes["Mounted Volumes"]
            cs["cost_structure/<br/>4 JSON fee files (ro)"]
            m9_art["ml_service/artifacts/m9/<br/>M9 v2 trained models"]
            tpv_art["ml_service/artifacts/tpv/<br/>TPV trained models"]
        end
    end

    nginx --> frontend
    nginx --> merchant
    nginx --> backend
    nginx --> mlservice

    frontend -.->|depends_on| backend
    merchant -.->|depends_on| backend
    backend -.->|depends_on| postgres
    mlservice -.->|depends_on| postgres

    backend --- cs
    mlservice --- m9_art
    mlservice --- tpv_art
    postgres --- vol_pg
```

## Project Directory Structure (Live Code Only)

```
404_found_us/
├── docker-compose.yml          # Service orchestration
├── nginx/
│   └── default.conf            # Reverse proxy routing rules
├── backend/                    # FastAPI — fee calculations & data management
│   ├── app.py                  # Entry point, CORS, lifespan
│   ├── config.py               # ML_SERVICE_URL, DB config
│   ├── database.py             # SQLAlchemy engine + session
│   ├── models.py               # ORM: transactions, merchants, calculation_results, upload_batches
│   ├── routes.py               # All /api/v1 endpoints
│   ├── schemas.py              # Pydantic request/response models
│   ├── services.py             # DataProcessing, MerchantFeeCalculation, MCC services
│   ├── validators.py           # CSV/Excel row validation
│   ├── Dockerfile
│   └── modules/
│       ├── cost_calculation/   # Interchange cost computation
│       └── merchant_quote/     # Quote generation with ML pipeline
├── ml_service/                 # FastAPI — ML engine orchestration
│   ├── app.py                  # Entry point, initializes M9 + TPV caches
│   ├── config.py               # VECTOR_DIM, SARIMA params, artifact paths
│   ├── database.py             # SQLAlchemy engine + session
│   ├── models.py               # ORM: knn_transactions, knn_cost_type_ref
│   ├── routes.py               # All /ml endpoints
│   ├── schemas.py              # Shared Pydantic models
│   ├── Dockerfile
│   ├── artifacts/
│   │   ├── m9/5411/{1,3,6}/    # M9 v2 cost forecast models
│   │   └── tpv/{4121,5411,5499,5812}/  # TPV forecast models
│   └── modules/
│       ├── cost_forecast/      # M9 v2 artifact-based cost prediction
│       ├── tpv_forecast/       # Conformal TPV prediction
│       ├── knn_rate_quote/     # KNN-based rate quotation
│       ├── rate_optimisation/  # Rate optimisation engine
│       ├── tpv_prediction/     # TPV prediction engine
│       ├── profit_forecast/    # Monte Carlo profit simulation
│       └── volume_forecast/    # SARIMAX weekly volume forecast
├── frontend/                   # React CRA — Sales calculator UI
│   ├── src/
│   │   ├── App.js              # View router: landing, current-rates, desired-margin
│   │   ├── components/
│   │   │   ├── LandingPage.jsx
│   │   │   ├── EnhancedMerchantFeeCalculator.jsx
│   │   │   ├── DesiredMarginCalculator.jsx
│   │   │   ├── ResultsPanel.jsx
│   │   │   ├── DataUploadValidator.jsx
│   │   │   ├── ManualTransactionEntry.jsx
│   │   │   └── MCCDropdown.jsx
│   │   ├── services/api.js     # Axios API client
│   │   ├── hooks/              # useFileValidation, useTransactionValidation
│   │   └── lib/ui/             # Shared UI primitives
│   └── Dockerfile
├── merchant-frontend/          # Vite + React + TypeScript — Merchant quotation UI
│   ├── src/
│   │   ├── App.tsx             # Form → Result state machine
│   │   └── components/
│   │       ├── QuotationForm.tsx
│   │       └── QuotationResult.tsx
│   └── Dockerfile
├── cost_structure/             # Payment card network fee JSON files (mounted ro)
│   ├── visa_Card.JSON
│   ├── visa_Network.JSON
│   ├── masterCard_Card.JSON
│   └── masterCard_Network.JSON
├── data/                       # Sample/test CSV datasets
└── archive/                    # Archived dead/legacy code
    ├── backend/errors.py
    ├── ml_service/
    │   ├── modules/{cluster_assignment, cluster_generation, m9_forecast}/
    │   ├── modules/cost_forecast/*_sarima_legacy.py
    │   └── migrate_sqlite_to_postgres.py
    ├── ml_pipeline/            # Training notebooks, EDA, Matt_EDA services
    ├── KNN Demo Service/       # Legacy KNN training data + SQLite DB
    ├── tools/                  # Standalone dev utilities
    └── scripts/                # One-time setup & git workflow PS1 scripts
```

## Technology Stack

```mermaid
%%{init: {'theme': 'base', 'themeVariables': { 'primaryColor': '#D6EAF8', 'primaryTextColor': '#1a1a2e', 'primaryBorderColor': '#4A90D9', 'lineColor': '#4A90D9', 'fontFamily': 'Segoe UI, sans-serif' }}}%%
graph LR
    subgraph infra["Infrastructure"]
        DC["Docker Compose"]
        NG["Nginx"]
        PG["PostgreSQL 16"]
    end

    subgraph backend_tech["Backend"]
        FA["FastAPI"]
        SA["SQLAlchemy"]
        PD["Pydantic"]
        HX["httpx"]
        PA["pandas"]
    end

    subgraph ml_tech["ML / Data Science"]
        SK["scikit-learn"]
        SM["statsmodels (SARIMAX)"]
        JB["joblib"]
        NP["numpy / scipy"]
    end

    subgraph frontend_tech["Frontend"]
        RE["React 18"]
        TW["Tailwind CSS"]
        AX["Axios"]
        VT["Vite (merchant)"]
        TS["TypeScript (merchant)"]
        RX["Radix UI (merchant)"]
        RC["Recharts (merchant)"]
    end

    style infra fill:#1B3A5C,stroke:#1B3A5C,stroke-width:2px,color:#ffffff
    style backend_tech fill:#4A90D9,stroke:#1B3A5C,stroke-width:2px,color:#ffffff
    style ml_tech fill:#4A90D9,stroke:#1B3A5C,stroke-width:2px,color:#ffffff
    style frontend_tech fill:#4A90D9,stroke:#1B3A5C,stroke-width:2px,color:#ffffff

    style DC fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style NG fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style PG fill:#D6EAF8,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style FA fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style SA fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style PD fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style HX fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style PA fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style SK fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style SM fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style JB fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style NP fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style RE fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style TW fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style AX fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style VT fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style TS fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style RX fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
    style RC fill:#ffffff,stroke:#4A90D9,stroke-width:2px,color:#1a1a2e
```
