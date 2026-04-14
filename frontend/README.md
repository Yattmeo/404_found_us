# Sales Frontend

React application for merchant fee calculation and profitability analysis. Served at `/sales/` via nginx.

> Part of the **404 Found Us** platform. See the [root README](../README.md) for the full architecture.

---

## Tools

### Merchant Profitability Calculator
Upload transaction CSV or enter manually → optionally set current rate and fixed fee → calculates interchange & network fees via ML pipeline (KNN + TPV + cost + profit forecast) → shows profitability metrics, cost forecast chart, volume trend, and probability curve.

- **Component**: `EnhancedMerchantFeeCalculator.jsx` → `ResultsPanel.jsx`
- **Endpoint**: `POST /api/v1/calculations/desired-margin-details` (desired margin hardcoded at 1.5%)

### Rates Quotation Tool
Upload merchant transaction history → set desired profit margin (bps) → optionally set current rate and fixed fee → get recommended rate with ML-driven cost forecast, volume forecast, Monte Carlo profit simulation, and profitability probability curve.

- **Component**: `DesiredMarginCalculator.jsx` → `DesiredMarginResults.jsx`
- **Endpoint**: `POST /api/v1/calculations/desired-margin-details`

> Both tools share the same backend endpoint and ML pipeline (4 sequential ML service calls). See [ARCHITECTURE.md](../ARCHITECTURE.md) for detailed data flow diagrams.

---

## Tech Stack

- **React** 18 (Create React App)
- **Tailwind CSS** — styling
- **React Hook Form** — form management
- **Axios** — HTTP client
- **Lucide React** — icons
- **XLSX** — Excel file parsing

---

## Components

```
src/components/
├── LandingPage.jsx                      Navigation / tool selection
├── EnhancedMerchantFeeCalculator.jsx    Profitability Calculator (input)
├── ResultsPanel.jsx                     Profitability Calculator results + charts
├── DesiredMarginCalculator.jsx          Rates Quotation tool (input)
├── DesiredMarginResults.jsx             Rates Quotation results + charts
├── DataUploadValidator.jsx              CSV/Excel upload with validation
├── ManualTransactionEntry.jsx           Manual transaction entry form
├── MCCDropdown.jsx                      MCC code selector
└── ui/                                  Shared UI primitives
```

---

## Development

```bash
# Standalone (outside Docker)
npm install
npm start          # http://localhost:3000

# Via Docker (normal workflow)
docker compose up frontend
```

API URL configured via `REACT_APP_BACKEND_URL` (defaults to `http://localhost/api/v1`).
