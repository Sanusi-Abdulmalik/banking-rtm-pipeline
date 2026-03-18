from pyspark.sql import DataFrame
from pyspark.sql import functions as F


# Typical max amount per transaction type
# Anything above these thresholds is suspicious
AMOUNT_THRESHOLDS = {
    "PURCHASE":   100_000,
    "WITHDRAWAL":  50_000,
    "TRANSFER":   300_000,
    "PAYMENT":     80_000,
    "REFUND":      30_000,
}


def apply_amount_check(df: DataFrame) -> DataFrame:
    """
    Flag transactions where the amount is suspiciously
    high for the given transaction type.
    Also flags card-testing pattern (amount < 1.00).
    """
    from functools import reduce

    # Build a dynamic WHEN/THEN expression from thresholds
    condition = reduce(
        lambda acc, item: acc.when(
            (F.col("transaction_type") == item[0]) &
            (F.col("amount") > item[1]),
            True
        ),
        AMOUNT_THRESHOLDS.items(),
        F.when(F.lit(False), False)
    )

    df = df.withColumn(
        "high_amount_flag",
        condition.otherwise(False)
    )

    # Card testing: very small amounts
    df = df.withColumn(
        "card_testing_flag",
        F.when(F.col("amount") < 1.0, True).otherwise(False)
    )

    df = df.withColumn(
        "amount_flag",
        F.col("high_amount_flag") | F.col("card_testing_flag")
    )

    return df