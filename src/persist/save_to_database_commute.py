import json
import psycopg2

# Connect to PostgreSQL
conn = psycopg2.connect(
    host="localhost",
    database="postgres",
    user="postgres",
    password="root"
)

def insert_cab_receipt(conn, data):

    cur = conn.cursor()

    sql = """
        INSERT INTO cab_receipts 
        (ride_id, date, time, pickup_address, drop_address, amount, distance, service_provider, ocr)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    values = (
        data.get("ride_id"),
        data.get("date"),
        data.get("time"),
        data.get("pickup_address"),
        data.get("drop_address"),
        data.get("amount"),
        data.get("distance"),
        data.get("service_provider"),
        data.get("ocr")
    )

    cur.execute(sql, values)
    conn.commit()

# Load all JSON entries
with open("rides.json", "r", encoding="utf-8") as f:
    records = json.load(f)

# Insert each record
for rec in records:
    insert_cab_receipt(conn, rec)

conn.close()

print("All records inserted successfully!")
