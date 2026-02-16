# Data Preprocessing Pipeline
This document outlines the three-step data preprocessing pipeline for preparing merchant transaction data for analysis.

## Overview
The preprocessing pipeline filters merchants by Merchant Category Code (MCC) and temporal criteria, then splits the data into training, validation, and test sets for machine learning purposes.

##Pipeline Steps

### Step 1: Merchant Selection via SQL

Identify merchants that were active in 2018 but inactive in 2019 for a specific MCC category.

SQL Query:

```
sql
SELECT DISTINCT merchant_id
FROM train
WHERE mcc = 4121
  AND merchant_id IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 4121
      AND YEAR(date) = 2018
  )
  AND merchant_id NOT IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 4121
      AND YEAR(date) = 2019
  )
ORDER BY merchant_id ASC;
```

Logic:
Filters transactions by MCC code, includes/excludes only merchants with transactions in 2018/2019
Returns unique merchant IDs in ascending order

Adaptation:
This query can be adapted for different MCC codes by replacing 4121 with the target category:
4121: Taxicabs/Limousines
5411: Grocery Stores/Supermarkets
5812: Eating Places/Restaurants

### Step 2: Train-Test-Validate Split

Objective: Split merchant data into training, validation, and test sets with proper stratification.

Implementation: Python notebook (train-test-split.ipynb)

Process Flow
+ For each MCC category, the script performs the following:
+ Load 2018-2019 Transaction Data
+ Load merchant IDs identified in Step 1. These represent merchants active in 2018 but not in 2019
+ Initial Split into three sets:
  + Train: 40% of total data
  + Validate: 35% of total data
  + Test: 25% of total data
+ Random seed: 404 
+ Load additional merchant IDs from 2018 dataset to Augment Training Set
+ Merge 2018 data into the training set. This increases training data volume while keeping validation and test sets clean
+ Export three CSV files per MCC category:
```
{mcc}_train.csv
{mcc}_validate.csv
{mcc}_test.csv
```

### Step 3: Calculate Processing Cost and Cost Type

Status: 🚧 Under Development

Objective: Compute processing costs and assign cost type identifiers for each merchant transaction.

Planned Features:
+ Calculate proc_cost based on transaction volumes and merchant characteristics 
+ Assign cost_type_id categories based on business rules
+ Integrate cost calculations with existing train/validate/test datasets

Implementation Details:

text
[PLACEHOLDER - To be completed]


After running the pipeline, verify:

+ No data leakage: Validate and test sets contain no merchant IDs from the augmented 2018 dataset
+ Temporal consistency: All merchants in validate/test sets are from the 2018-2019 filtered group
+ Split ratios: Confirm approximate distribution matches expected ratios
+ No duplicates: Ensure no merchant_id appears in multiple splits

### Notes
+ The pipeline ensures temporal integrity by preventing future data leakage.
+ Merchants in validation and test sets represent those that ceased operations in 2019
+ The training set includes both active (2018-2019) and 2018-only merchants
+ Random seeds are fixed for reproducibility across runs

### Authors & Maintenance
Created: 2026 Feb

Last Updated: February 2026

Maintainer: Denzel / 404_found_us
