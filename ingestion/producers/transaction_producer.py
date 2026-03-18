import json
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from confluent_kafka import Producer
from dotenv import load_dotenv
from faker import Faker

load_dotenv()

fake = Faker()

# ── Config ────────────────────────────────────────────────────────────────────
BOOTSTRAP_SERVERS = "localhost:9092"
TOPIC             = "raw-transactions"
TRANSACTIONS_PER_SECOND = 5   # increase this later to simulate load

# ── Reference data ────────────────────────────────────────────────────────────
TRANSACTION_TYPES = ["PURCHASE", "WITHDRAWAL", "TRANSFER", "PAYMENT", "REFUND"]

CHANNELS = ["ATM", "POS", "MOBILE", "ONLINE", "BRANCH"]

MERCHANT_CATEGORIES = [
    "GROCERY", "FUEL", "RESTAURANT", "RETAIL",
    "PHARMACY", "ELECTRONICS", "TRAVEL", "ENTERTAINMENT",
]

MERCHANTS = {
    "GROCERY":       ["Shoprite", "PriceSmart", "Spar", "Checkers"],
    "FUEL":          ["TotalEnergies", "Shell", "Mobil", "Oando"],
    "RESTAURANT":    ["KFC", "McDonald's", "Chicken Republic", "Domino's"],
    "RETAIL":        ["Jumia", "Konga", "H&M", "Zara"],
    "PHARMACY":      ["HealthPlus", "MedPlus", "Pharmacy One"],
    "ELECTRONICS":   ["Slot", "Samsung Store", "iStore", "3CHub"],
    "TRAVEL":        ["Air Peace", "Ethiopian Airlines", "Uber", "Bolt"],
    "ENTERTAINMENT": ["Netflix", "Showmax", "Cinema One", "DSTV"],
}

LOCATIONS = [
    ("Lagos",    "Nigeria",    6.5244,  3.3792),
    ("Abuja",    "Nigeria",    9.0579,  7.4951),
    ("Ibadan",   "Nigeria",    7.3775,  3.9470),
    ("Kano",     "Nigeria",   12.0022,  8.5920),
    ("London",   "UK",        51.5074, -0.1278),
    ("New York", "USA",       40.7128,-74.0060),
    ("Dubai",    "UAE",       25.2048, 55.2708),
    ("Accra",    "Ghana",      5.6037, -0.1870),
]

CURRENCIES = ["NGN", "USD", "GBP", "EUR", "AED", "GHS"]

STATUSES = ["SUCCESS", "SUCCESS", "SUCCESS", "SUCCESS", "FAILED", "PENDING"]
# SUCCESS appears 4x to make it more realistic


# ── Fraud simulation ──────────────────────────────────────────────────────────
def maybe_inject_fraud(transaction: dict) -> dict:
    """
    Randomly inject fraud patterns into ~5% of transactions
    so our fraud detection logic has something to catch.
    """
    if random.random() > 0.05:
        return transaction

    fraud_pattern = random.choice(["high_amount", "foreign_location", "rapid_fire"])

    if fraud_pattern == "high_amount":
        # Suspiciously large amount
        transaction["amount"] = round(random.uniform(50_000, 500_000), 2)

    elif fraud_pattern == "foreign_location":
        # Transaction from an unusual foreign location
        transaction["location_city"]    = "Moscow"
        transaction["location_country"] = "Russia"
        transaction["latitude"]         = 55.7558
        transaction["longitude"]        = 37.6173

    elif fraud_pattern == "rapid_fire":
        # Very small amount — card testing pattern
        transaction["amount"] = round(random.uniform(0.01, 1.00), 2)

    return transaction


# ── Transaction generator ─────────────────────────────────────────────────────
def generate_transaction() -> dict:
    category                  = random.choice(MERCHANT_CATEGORIES)
    merchant                  = random.choice(MERCHANTS[category])
    city, country, lat, lon   = random.choice(LOCATIONS)
    currency                  = random.choice(CURRENCIES)

    # Amount ranges by transaction type
    txn_type = random.choice(TRANSACTION_TYPES)
    amount_ranges = {
        "PURCHASE":   (500,    150_000),
        "WITHDRAWAL": (1_000,   50_000),
        "TRANSFER":   (5_000,  500_000),
        "PAYMENT":    (200,    100_000),
        "REFUND":     (200,     50_000),
    }
    lo, hi = amount_ranges[txn_type]
    amount = round(random.uniform(lo, hi), 2)

    transaction = {
        "transaction_id":    str(uuid.uuid4()),
        "account_id":        f"ACC{random.randint(100000, 999999)}",
        "customer_name":     fake.name(),
        "amount":            amount,
        "currency":          currency,
        "transaction_type":  txn_type,
        "channel":           random.choice(CHANNELS),
        "merchant_name":     merchant,
        "merchant_category": category,
        "location_city":     city,
        "location_country":  country,
        "latitude":          lat + random.uniform(-0.01, 0.01),
        "longitude":         lon + random.uniform(-0.01, 0.01),
        "timestamp":         datetime.now(timezone.utc).isoformat(),
        "status":            random.choice(STATUSES),
        "device_id":         f"DEV{random.randint(10000, 99999)}",
        "ip_address":        fake.ipv4(),
    }

    return maybe_inject_fraud(transaction)


# ── Kafka callbacks ───────────────────────────────────────────────────────────
def delivery_report(err, msg):
    if err:
        print(f"  ❌ Delivery failed: {err}")
    else:
        print(
            f"  ✅ Sent → partition={msg.partition()} "
            f"offset={msg.offset()} "
            f"key={msg.key().decode()}"
        )


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    producer = Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})

    print(f"🏦 Banking Transaction Producer started")
    print(f"   Topic  : {TOPIC}")
    print(f"   Rate   : {TRANSACTIONS_PER_SECOND} transactions/sec")
    print(f"   Broker : {BOOTSTRAP_SERVERS}")
    print(f"   Press Ctrl+C to stop\n")

    total_sent = 0

    try:
        while True:
            for _ in range(TRANSACTIONS_PER_SECOND):
                txn        = generate_transaction()
                key        = txn["account_id"]          # partition by account
                value      = json.dumps(txn).encode("utf-8")

                producer.produce(
                    topic          = TOPIC,
                    key            = key.encode("utf-8"),
                    value          = value,
                    on_delivery    = delivery_report,
                )

                total_sent += 1

            producer.poll(0)       # trigger delivery callbacks
            print(f"\n📊 Total sent: {total_sent} transactions\n")
            time.sleep(1)          # wait 1 second before next batch

    except KeyboardInterrupt:
        print(f"\n⏹  Producer stopped. Total sent: {total_sent}")

    finally:
        print("🔄 Flushing remaining messages...")
        producer.flush()
        print("✅ Done.")


if __name__ == "__main__":
    main()