# Isolated Service Lab

This directory contains isolated copies of the production-style services and a
local SQLite database for notebook-based testing.

## Contents

- services/KNN Quote Service Production
- services/GetCostForecast Service
- services/GetVolumeForecast Service
- data/processed_transactions_4mcc.csv
- data/isolated_services.sqlite
- outputs/
- isolated_service_testing.ipynb
- isolated_multi_merchant_volume_eval.ipynb

## Purpose

Use this lab to run the services, modify copied code, and perform local tests
without affecting the primary service directories under Matt_EDA/services.

## Local Database

The KNN service in this lab should point to:

- data/isolated_services.sqlite

That SQLite file includes:

- transactions
- cost_type_ref

## Notebook

Open isolated_service_testing.ipynb to:

1. verify copied paths
2. rebuild the SQLite database if needed
3. start isolated KNN, cost, and volume services
4. call the endpoints against the isolated copies
5. stop the services cleanly

Open isolated_multi_merchant_volume_eval.ipynb to:

1. rebuild a lab-local SQLite database from sampled reference merchants
2. start isolated KNN and volume services only for evaluation
3. evaluate multiple target merchants against held-out weekly totals
4. save metrics JSON and panel plots under outputs/multi_volume
5. stop the services cleanly after the run
