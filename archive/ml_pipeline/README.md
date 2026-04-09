# ML Pipeline

EDA notebooks, model prototyping, service development, and pre-processing scripts.

> Part of the **404 Found Us** platform. See the [root README](../README.md) for the full architecture.

---

## Structure

```
ml_pipeline/
├── Matt_EDA/                     Primary EDA & service development
│   ├── Clustering/                   Clustering analysis (base cost, txn type features)
│   ├── Supervised learning/          Supervised model experiments
│   ├── KNN Demo Service/             KNN rate quote service prototype
│   ├── isolated_service_lab/         Service integration testing
│   ├── service_eval_outputs/         Evaluation outputs
│   └── services/                     Production service code
│       ├── GetAvgProcCostForecast Service v2/   M9 monthly cost forecast (deployed)
│       ├── GetCostForecast Service/             SARIMA cost forecast (legacy)
│       ├── GetVolumeForecast Service/           SARIMA volume forecast (deployed)
│       └── KNN Quote Service Production/        KNN quote service (deployed)
├── forecasting/                  SARIMA notebooks & scripts
│   ├── sarima.py / sarima_live.py / sarima_service.py
│   └── MattSARIMA/                   SARIMA experiments
├── pre-processing/               Data extraction & train/test splits
│   ├── 01_extract_merchant_IDs.sql
│   ├── 02_train_test_split.ipynb
│   ├── 03_Apply_Txn_Proc_Cost.ipynb
│   └── {4121,5411,5812}_{train,test,validate}.csv
├── tree_models/                  Tree-based model prototypes
├── EDA/                          Archived EDA notebooks
└── 4121_clustering_B_v2.ipynb    Clustering notebook
```

## Deployed Services

| Service | Container | Port | Model |
|---------|-----------|------|-------|
| M9 Cost Forecast | m9-forecast-service | 8092 | HuberRegressor + GBR conformal intervals |
| Volume Forecast | ml-service (module) | 8001 | SARIMA/SARIMAX weekly |
| KNN Quote | ml-service (module) | 8001 | k=5 Euclidean nearest neighbours |
| Cost Forecast Proxy | ml-service (module) | 8001 | Proxies to M9, interpolates monthly→weekly |

## Pre-processed Datasets

MCC-specific train/test/validate splits in `pre-processing/`:
- **4121** — Transportation
- **5411** — Grocery Stores
- **5812** — Restaurants
