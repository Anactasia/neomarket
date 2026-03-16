import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5433,
    database="neomarket_b2b",
    user="postgres",
    password="postgres"
)

print("connected")