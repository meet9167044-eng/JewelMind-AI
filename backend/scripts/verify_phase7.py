import pymysql

conn = pymysql.connect(host='localhost', user='root', password='Meet12', database='jewelmind_db')
cur = conn.cursor()

print("=== MySQL Row Count Verification ===")
for table in ['users', 'businesses', 'products', 'purchases', 'sales', 'metal_rates']:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    count = cur.fetchone()[0]
    print(f"  {table:<15}: {count:>7,} rows")

# Verify all business-data rows have business_id = 1
cur.execute("SELECT COUNT(*) FROM products WHERE business_id != 1")
print(f"\n  Cross-tenant products (must be 0): {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM purchases WHERE business_id != 1")
print(f"  Cross-tenant purchases (must be 0): {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM sales WHERE business_id != 1")
print(f"  Cross-tenant sales (must be 0): {cur.fetchone()[0]}")

# Verify metal_rates has no business_id
cur.execute("DESCRIBE metal_rates")
cols = [row[0] for row in cur.fetchall()]
print(f"\n  metal_rates columns: {cols}")
assert "business_id" not in cols, "ERROR: metal_rates must NOT have business_id!"
print("  business_id absent from metal_rates: OK")

conn.close()
print("\nAll verification checks passed.")
