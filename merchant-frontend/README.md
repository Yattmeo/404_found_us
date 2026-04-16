# Merchant Frontend

Vite + React + TypeScript application for the online merchant quotation tool. Served at `/merchant/` via nginx.

> Part of the **404 Found Us** platform. See the [root README](../README.md) for the full architecture.

---

## What It Does

Self-service quotation tool for merchants. The user fills in business details (industry, average transaction value, monthly volume, card mix, channel split) and receives a rate quote with breakdowns.

- **Form → Result** two-step flow
- Calls `POST /api/v1/merchant-quote` with business data
- Falls back to a client-side placeholder quote if the backend/ML service is unavailable

---

## Tech Stack

- **React** 18
- **TypeScript**
- **Vite** (with SWC plugin)
- **Tailwind CSS** — styling
- **Radix UI** — accessible component primitives
- **Recharts** — charts
- **React Hook Form** — form management
- **Axios** — HTTP client
- **Lucide React** — icons
- **Vitest** + **Testing Library** — testing

---

## Components

```
src/
├── App.tsx                  Main app — form/result state machine
├── main.tsx                 Entry point
├── index.css                Tailwind imports
├── assets/
│   ├── logo.svg
│   └── illustration.svg
├── components/
│   ├── QuotationForm.tsx    Business details input form
│   └── QuotationResult.tsx  Quote display with rate breakdowns
└── __tests__/
    ├── setup.ts
    ├── components/
    │   ├── App.test.tsx
    │   ├── QuotationForm.test.tsx
    │   └── QuotationResult.test.tsx
    └── integration/
        └── merchant-tool.integration.test.tsx
```

---

## Development

```bash
# Standalone (outside Docker)
npm install
npm run dev        # http://localhost:3001

# Via Docker (normal workflow)
docker compose up merchant-frontend
```

API URL configured via `VITE_API_BASE_URL` (defaults to `/api/v1`).

---

## Testing

```bash
npm test           # single run (vitest run)
npm run test:watch # watch mode
```

---

## Build

```bash
npm run build      # outputs to build/
```

Multi-stage Docker build: Vite build → served with `serve` on port 3001.
