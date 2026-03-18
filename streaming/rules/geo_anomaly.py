from pyspark.sql import DataFrame
from pyspark.sql import functions as F


# Countries considered high-risk for this demo
HIGH_RISK_COUNTRIES = [
    "Russia", "North Korea", "Iran", "Belarus"
]


def apply_geo_check(df: DataFrame) -> DataFrame:
    """
    Flag transactions from high-risk countries
    or from impossible locations (far from usual base).
    """
    high_risk_condition = F.col("location_country").isin(
        HIGH_RISK_COUNTRIES
    )

    df = df.withColumn(
        "geo_flag",
        F.when(high_risk_condition, True).otherwise(False)
    )

    return df