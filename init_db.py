"""
init_db.py — S2P-Audit-Core Mock ERP Database Initialization

Creates and seeds an SQLite database (erp_system.db) with Purchase Order
and Goods Receipt data that includes edge cases for three-way match testing.

Edge Cases:
  PO-001: Perfect match scenario
  PO-002: Partial Goods Receipt (Ordered 100, Received 50)
  PO-003: Vendor name typo ("GlobalTech India" vs expected "GlobalTech Pvt Ltd")
"""

import sqlite3
import os
from datetime import datetime, timedelta


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "erp_system.db")


def create_tables(conn: sqlite3.Connection) -> None:
    """Create the po_master and gr_records tables."""
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS po_master")
    cursor.execute("DROP TABLE IF EXISTS gr_records")

    cursor.execute("""
        CREATE TABLE po_master (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number       TEXT    NOT NULL,
            vendor_name     TEXT    NOT NULL,
            item_desc       TEXT    NOT NULL,
            qty             REAL    NOT NULL,
            unit_price      REAL    NOT NULL,
            total_value     REAL    NOT NULL,
            status          TEXT    NOT NULL DEFAULT 'ACTIVE',
            created_at      TEXT    NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE gr_records (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            gr_number       TEXT    NOT NULL,
            po_number       TEXT    NOT NULL,
            item_desc       TEXT    NOT NULL,
            received_qty    REAL    NOT NULL,
            receipt_date    TEXT    NOT NULL,
            quality_status  TEXT    NOT NULL DEFAULT 'ACCEPTED'
        )
    """)

    conn.commit()


def seed_data(conn: sqlite3.Connection) -> None:
    """Insert seed data for three edge-case Purchase Orders and their Goods Receipts."""
    cursor = conn.cursor()
    now = datetime.now()

    # ---------------------------------------------------------------
    # PO-001: Perfect match — Ordered 50, Received 50
    # ---------------------------------------------------------------
    po_001_items = [
        ("PO-001", "Acme Corp", "Laptop Dell Latitude 5540",   50.0,  1200.00, 60000.00, "ACTIVE", (now - timedelta(days=30)).isoformat()),
        ("PO-001", "Acme Corp", "Wireless Mouse Logitech MX",  50.0,    45.00,  2250.00, "ACTIVE", (now - timedelta(days=30)).isoformat()),
    ]

    gr_001_items = [
        ("GR-001", "PO-001", "Laptop Dell Latitude 5540",   50.0, (now - timedelta(days=15)).strftime("%Y-%m-%d"), "ACCEPTED"),
        ("GR-002", "PO-001", "Wireless Mouse Logitech MX",  50.0, (now - timedelta(days=15)).strftime("%Y-%m-%d"), "ACCEPTED"),
    ]

    # ---------------------------------------------------------------
    # PO-002: Partial receipt — Ordered 100, Received 50
    # ---------------------------------------------------------------
    po_002_items = [
        ("PO-002", "TechSupply Inc", "Server Rack Unit 42U",  100.0,   50.00, 5000.00, "ACTIVE", (now - timedelta(days=20)).isoformat()),
    ]

    gr_002_items = [
        ("GR-003", "PO-002", "Server Rack Unit 42U", 50.0, (now - timedelta(days=10)).strftime("%Y-%m-%d"), "ACCEPTED"),
    ]

    # ---------------------------------------------------------------
    # PO-003: Vendor name typo — PO says "GlobalTech India", invoice may say "GlobalTech Pvt Ltd"
    # ---------------------------------------------------------------
    po_003_items = [
        ("PO-003", "GlobalTech India", "Cloud Hosting Annual License", 1.0, 25000.00, 25000.00, "ACTIVE", (now - timedelta(days=45)).isoformat()),
    ]

    gr_003_items = [
        ("GR-004", "PO-003", "Cloud Hosting Annual License", 1.0, (now - timedelta(days=5)).strftime("%Y-%m-%d"), "ACCEPTED"),
    ]

    # Insert PO master data
    all_pos = po_001_items + po_002_items + po_003_items
    cursor.executemany(
        "INSERT INTO po_master (po_number, vendor_name, item_desc, qty, unit_price, total_value, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        all_pos,
    )

    # Insert GR records
    all_grs = gr_001_items + gr_002_items + gr_003_items
    cursor.executemany(
        "INSERT INTO gr_records (gr_number, po_number, item_desc, received_qty, receipt_date, quality_status) VALUES (?, ?, ?, ?, ?, ?)",
        all_grs,
    )

    conn.commit()


def main() -> None:
    """Main entry point — creates the database, tables, and seeds data."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"♻  Removed existing database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    print(f"📦 Creating database: {DB_PATH}")

    create_tables(conn)
    print("✅ Tables created: po_master, gr_records")

    seed_data(conn)

    # Verification
    cursor = conn.cursor()
    po_count = cursor.execute("SELECT COUNT(*) FROM po_master").fetchone()[0]
    gr_count = cursor.execute("SELECT COUNT(*) FROM gr_records").fetchone()[0]
    print(f"✅ Seeded {po_count} PO line items and {gr_count} GR records")

    # Print summary
    print("\n📋 PO Master Summary:")
    for row in cursor.execute("SELECT po_number, vendor_name, item_desc, qty, unit_price FROM po_master"):
        print(f"   {row[0]} | {row[1]:20s} | {row[2]:35s} | Qty: {row[3]:>6.0f} | Price: ${row[4]:>10.2f}")

    print("\n📋 GR Records Summary:")
    for row in cursor.execute("SELECT gr_number, po_number, item_desc, received_qty, quality_status FROM gr_records"):
        print(f"   {row[0]} | {row[1]} | {row[2]:35s} | Received: {row[3]:>6.0f} | {row[4]}")

    conn.close()
    print("\n🚀 Database initialization complete!")


if __name__ == "__main__":
    main()
