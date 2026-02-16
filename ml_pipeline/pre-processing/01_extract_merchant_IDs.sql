-- mcc 4121, year 2018
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
-- mcc 4121, year 2019
SELECT DISTINCT merchant_id
FROM train
WHERE mcc = 4121
  AND merchant_id NOT IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 4121
      AND YEAR(date) = 2018
  )
  AND merchant_id IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 4121
      AND YEAR(date) = 2019
  )
ORDER BY merchant_id ASC;
-- mcc 4121, year 2018 & 2019
SELECT DISTINCT merchant_id
FROM train
WHERE mcc = 4121
  AND merchant_id IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 4121
      AND YEAR(date) = 2018
  )
  AND merchant_id IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 4121
      AND YEAR(date) = 2019
  )
ORDER BY merchant_id ASC;
-- mcc 5411, year 2018
SELECT DISTINCT merchant_id
FROM train
WHERE mcc = 5411
  AND merchant_id IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 5411
      AND YEAR(date) = 2018
  )
  AND merchant_id NOT IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 5411
      AND YEAR(date) = 2019
  )
ORDER BY merchant_id ASC;
-- mcc 5411, year 2019
-SELECT DISTINCT merchant_id
FROM train
WHERE mcc = 5411
  AND merchant_id NOT IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 5411
      AND YEAR(date) = 2018
  )
  AND merchant_id IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 5411
      AND YEAR(date) = 2019
  )
ORDER BY merchant_id ASC;
-- mcc 5411 year 2018 & 2019
SELECT DISTINCT merchant_id
FROM train
WHERE mcc = 5411
  AND merchant_id IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 5411
      AND YEAR(date) = 2018
  )
  AND merchant_id IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 5411
      AND YEAR(date) = 2019
  )
ORDER BY merchant_id ASC;
-- mcc 5812 year 2018
SELECT DISTINCT merchant_id
FROM train
WHERE mcc = 5812
  AND merchant_id IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 5812
      AND YEAR(date) = 2018
  )
  AND merchant_id NOT IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 5812
      AND YEAR(date) = 2019
  )
ORDER BY merchant_id ASC;
-- mcc 5812 year 2019
SELECT DISTINCT merchant_id
FROM train
WHERE mcc = 5812
  AND merchant_id NOT IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 5812
      AND YEAR(date) = 2018
  )
  AND merchant_id IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 5812
      AND YEAR(date) = 2019
  )
ORDER BY merchant_id ASC;
-- mcc 5812 year 2018 & 2019
SELECT DISTINCT merchant_id
FROM train
WHERE mcc = 5812
  AND merchant_id IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 5812
      AND YEAR(date) = 2018
  )
  AND merchant_id NOT IN (
    SELECT merchant_id
    FROM train
    WHERE mcc = 5812
      AND YEAR(date) = 2019
  )
ORDER BY merchant_id ASC;
