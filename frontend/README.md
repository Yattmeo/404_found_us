# Merchant Fee Calculator - Frontend

A dynamic React application for merchant fee calculation and profitability analysis.

## Features

- **Merchant Profitability Calculator**: Assess profitability based on current merchant rates and transaction data
- **Rates Quotation Tool**: Analyze merchant profiles and recommend suitable pricing
- **Data Upload**: Support for CSV file uploads with validation
- **Manual Entry**: Enter transaction data manually
- **API Integration**: Full backend integration for dynamic calculations
- **Responsive Design**: Beautiful UI with Tailwind CSS

## Prerequisites

- Node.js (v14 or higher)
- npm or yarn

## Installation

1. Install dependencies:
```bash
npm install
```

2. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

3. Update the API URL in `.env` if needed

## Running the Application

### Development Mode
```bash
npm start
```

The application will open at [http://localhost:3000](http://localhost:3000)

### Production Build
```bash
npm run build
```

## Project Structure

```
frontend/
├── public/
├── src/
│   ├── components/
│   │   ├── ui/              # Reusable UI components
│   │   ├── LandingPage.jsx
│   │   ├── EnhancedMerchantFeeCalculator.jsx
│   │   ├── DesiredMarginCalculator.jsx
│   │   ├── ResultsPanel.jsx
│   │   ├── DesiredMarginResults.jsx
│   │   ├── DataUploadValidator.jsx
│   │   ├── ManualTransactionEntry.jsx
│   │   └── MCCDropdown.jsx
│   ├── services/
│   │   └── api.js           # API service layer
│   ├── lib/
│   │   └── utils.js         # Utility functions
│   ├── App.js
│   ├── App.css
│   └── index.js
├── tailwind.config.js
├── postcss.config.js
└── package.json
```

## API Integration

The application connects to the backend API for:
- Transaction data upload and validation
- Current rate profitability calculations
- Desired margin quotation calculations
- MCC code lookups

All API calls are handled through the `services/api.js` module.

## Technologies Used

- **React** 18.3.1
- **React Hook Form** - Form management
- **Tailwind CSS** - Styling
- **Lucide React** - Icons
- **Axios** - HTTP client
- **XLSX** - Excel file parsing

## Available Scripts

- `npm start` - Run development server
- `npm run build` - Create production build
- `npm test` - Run tests
- `npm run eject` - Eject from Create React App

## Features Overview

### Current Rates Calculator
- Upload transaction CSV or enter manually
- Configure fee structure (percentage, fixed, or both)
- View profitability metrics and suggested rates
- Compare with current rates if provided

### Desired Margin Calculator
- Upload merchant transaction history
- Set desired profit margin
- Get rate quotations and ranges
- View expected metrics with error margins
