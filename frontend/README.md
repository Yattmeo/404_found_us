# Sales Frontend

React application for merchant fee calculation and profitability analysis. Served at `/sales/` via nginx.

> Part of the **404 Found Us** platform. See the [root README](../README.md) for the full architecture.

---

## Tools

### Merchant Profitability Calculator
Upload transaction CSV or enter manually → calculates interchange & network fees → shows profitability metrics, cost forecast chart, volume trend, and probability curve.

### Rates Quotation Tool
Upload merchant transaction history → set desired profit margin → get recommended rate with ML-driven cost forecast (12-week), volume forecast (12-week), and profitability probability curve.

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
├── EnhancedMerchantFeeCalculator.jsx    Current Rates tool (input + results)
├── DesiredMarginCalculator.jsx          Desired Margin tool (input)
├── DesiredMarginResults.jsx             Desired Margin results + charts
├── ResultsPanel.jsx                     Profitability Calculator results + charts
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
