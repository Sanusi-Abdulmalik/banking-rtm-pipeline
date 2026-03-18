import os
from pathlib import Path

from dotenv import load_dotenv
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    StringType,
    StructField,
    StructType,
)

import sys
sys.path.append(str(Path(__file__).resolve().parents[2]))

from streaming.rules.amount_deviation import apply_amount_check
from streaming.rules.geo_anomaly import apply_geo_check
from streaming.rules.velocity_check import apply_velocity_check

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
KAFKA_BROKER      = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC       = os.getenv("KAFKA_TOPIC_TRANSACTIONS", "raw-transactions")
DELTA_LAKE_PATH   = os.getenv("DELTA_LAKE_PATH", "./data/delta")
CHECKPOINT_PATH   = "./data/checkpoints/fraud_detection"

BRONZE_PATH       = f"{DELTA_LAKE_PATH}/bronze/transactions"
GOLD_PATH         = f"{DELTA_LAKE_PATH}/gold/fraud_alerts"

# ── Transaction schema ────────────────────────────────────────────────────────
TRANSACTION_SCHEMA = StructType([
    StructField("transaction_id",    StringType(), True),
    StructField("account_id",        StringType(), True),
    StructField("customer_name",     StringType(), True),
    StructField("amount",            DoubleType(), True),
    StructField("currency",          StringType(), True),
    StructField("transaction_type",  StringType(), True),
    StructField("channel",           StringType(), True),
    StructField("merchant_name",     StringType(), True),
    StructField("merchant_category", StringType(), True),
    StructField("location_city",     StringType(), True),
    StructField("location_country",  StringType(), True),
    StructField("latitude",          DoubleType(), True),
    StructField("longitude",         DoubleType(), True),
    StructField("timestamp",         StringType(), True),
    StructField("status",            StringType(), True),
    StructField("device_id",         StringType(), True),
    StructField("ip_address",        StringType(), True),
])


# ── Spark session ─────────────────────────────────────────────────────────────
def create_spark_session() -> SparkSession:
    return (
        SparkSession.builder
        .appName("FraudDetectionStream")
        .master("local[*]")
        .config(
            "spark.jars.packages",
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
            "io.delta:delta-spark_2.12:3.2.0"
        )
        .config("spark.sql.extensions",
                "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog",
                "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.driver.memory", "2g")
        .getOrCreate()
    )


# ── Read from Kafka ───────────────────────────────────────────────────────────
def read_kafka_stream(spark: SparkSession):
    return (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BROKER)
        .option("subscribe", KAFKA_TOPIC)
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .load()
    )


# ── Parse JSON payload ────────────────────────────────────────────────────────
def parse_transactions(raw_df):
    return (
        raw_df
        .select(
            F.from_json(
                F.col("value").cast("string"),
                TRANSACTION_SCHEMA
            ).alias("data")
        )
        .select("data.*")
        .filter(F.col("transaction_id").isNotNull())
    )


# ── Apply fraud rules ─────────────────────────────────────────────────────────
def apply_fraud_rules(df):
    df = apply_velocity_check(df)
    df = apply_amount_check(df)
    df = apply_geo_check(df)

    # Master fraud flag — any rule triggered = fraud suspect
    df = df.withColumn(
        "is_fraud_suspect",
        F.col("velocity_flag") |
        F.col("amount_flag")   |
        F.col("geo_flag")
    )

    # Risk score: count how many rules fired (0–3)
    df = df.withColumn(
        "risk_score",
        F.col("velocity_flag").cast("int") +
        F.col("amount_flag").cast("int")   +
        F.col("geo_flag").cast("int")
    )

    # Risk level label
    df = df.withColumn(
        "risk_level",
        F.when(F.col("risk_score") == 0, "LOW")
         .when(F.col("risk_score") == 1, "MEDIUM")
         .when(F.col("risk_score") == 2, "HIGH")
         .otherwise("CRITICAL")
    )

    # Add processing timestamp
    df = df.withColumn(
        "processed_at",
        F.current_timestamp()
    )

    return df


# ── Write to console (for debugging) ─────────────────────────────────────────
def write_to_console(df, checkpoint_path: str):
    return (
        df.writeStream
        .outputMode("append")
        .format("console")
        .option("truncate", False)
        .option("numRows", 10)
        .option("checkpointLocation", f"{checkpoint_path}/console")
        .trigger(processingTime="10 seconds")
        .start()
    )


# ── Write bronze layer (all transactions) ────────────────────────────────────
def write_bronze(df, checkpoint_path: str):
    return (
        df.writeStream
        .outputMode("append")
        .format("parquet")
        .option("path", BRONZE_PATH)
        .option("checkpointLocation", f"{checkpoint_path}/bronze")
        .trigger(processingTime="10 seconds")
        .start()
    )


# ── Write gold layer (fraud suspects only) ───────────────────────────────────
def write_fraud_alerts(df, checkpoint_path: str):
    fraud_df = df.filter(F.col("is_fraud_suspect") == True)

    return (
        fraud_df.writeStream
        .outputMode("append")
        .format("parquet")
        .option("path", GOLD_PATH)
        .option("checkpointLocation", f"{checkpoint_path}/fraud_alerts")
        .trigger(processingTime="10 seconds")
        .start()
    )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("🚀 Starting Fraud Detection Streaming Job...")
    print(f"   Kafka broker : {KAFKA_BROKER}")
    print(f"   Topic        : {KAFKA_TOPIC}")
    print(f"   Bronze path  : {BRONZE_PATH}")
    print(f"   Gold path    : {GOLD_PATH}\n")

    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    # Create checkpoint directories
    Path(CHECKPOINT_PATH).mkdir(parents=True, exist_ok=True)
    Path(BRONZE_PATH).mkdir(parents=True, exist_ok=True)
    Path(GOLD_PATH).mkdir(parents=True, exist_ok=True)

    # Pipeline
    raw_df      = read_kafka_stream(spark)
    parsed_df   = parse_transactions(raw_df)
    enriched_df = apply_fraud_rules(parsed_df)

    # Start all three write streams
    console_query = write_to_console(enriched_df, CHECKPOINT_PATH)
    bronze_query  = write_bronze(parsed_df, CHECKPOINT_PATH)
    fraud_query   = write_fraud_alerts(enriched_df, CHECKPOINT_PATH)

    print("✅ Streaming queries started. Waiting for data...\n")

    # Keep running until Ctrl+C
    try:
        console_query.awaitTermination()
    except KeyboardInterrupt:
        print("\n⏹  Stopping streaming job...")
        console_query.stop()
        bronze_query.stop()
        fraud_query.stop()
        print("✅ All streams stopped.")


if __name__ == "__main__":
    main()