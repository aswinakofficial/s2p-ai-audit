"""
init_db.py — S2P AI Audit: Mock ERP Database Initialization (V2)

Creates and seeds an SQLite database (erp_system.db) with:
  - po_master:        Purchase Order line items
  - gr_records:       Goods Receipt records
  - vendor_master:    Normalized vendor registry with addresses & tax IDs
  - invoice_history:  Audit trail for every processed invoice

Seed Data Edge Cases:
  PO-001: Perfect match scenario
  PO-002: Partial Goods Receipt (Ordered 100, Received 50)
  PO-003: Vendor name typo ("GlobalTech India" vs "GlobalTech Pvt Ltd")
  PO-004: Price mismatch ($52 invoice vs $50 PO — triggers 1% tolerance)
  PO-005: Multi-line PO with mixed pass/fail items
  PO-006: Duplicate invoice detection scenario
"""

import sqlite3
import os
from datetime import datetime, timedelta


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "erp_system.db")


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all database tables."""
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS po_master")
    cursor.execute("DROP TABLE IF EXISTS gr_records")
    cursor.execute("DROP TABLE IF EXISTS vendor_master")
    cursor.execute("DROP TABLE IF EXISTS invoice_history")

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

    cursor.execute("""
        CREATE TABLE vendor_master (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_code     TEXT    NOT NULL UNIQUE,
            vendor_name     TEXT    NOT NULL,
            alternate_names TEXT,
            address         TEXT,
            tax_id          TEXT,
            risk_tier       TEXT    NOT NULL DEFAULT 'LOW',
            created_at      TEXT    NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE invoice_history (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_file    TEXT    NOT NULL,
            po_number       TEXT,
            vendor_name     TEXT,
            invoice_total   REAL,
            status          TEXT    NOT NULL,
            confidence      REAL,
            total_variances INTEGER DEFAULT 0,
            flags           TEXT,
            audit_report    TEXT,
            processed_at    TEXT    NOT NULL
        )
    """)

    conn.commit()


def seed_data(conn: sqlite3.Connection) -> None:
    """Insert seed data with 6 edge-case Purchase Orders."""
    cursor = conn.cursor()
    now = datetime.now()

    # ── Vendor Master ──────────────────────────────────────
    vendors = [
        ("V-001", "Acme Corp",        "Acme Corporation",         "123 Industrial Ave, Chicago, IL",       "TAX-ACME-001",   "LOW",    now.isoformat()),
        ("V-002", "TechSupply Inc",   "Tech Supply, TechSupply",  "456 Tech Park, Austin, TX",             "TAX-TECH-002",   "LOW",    now.isoformat()),
        ("V-003", "GlobalTech India", "GlobalTech Pvt Ltd",       "789 IT Corridor, Bangalore, India",     "GSTIN-GT-003",   "MEDIUM", now.isoformat()),
        ("V-004", "NexGen Solutions", "NexGen, Nexgen Solutions",  "321 Innovation Blvd, San Jose, CA",     "TAX-NXG-004",    "LOW",    now.isoformat()),
        ("V-005", "PrimeParts Ltd",   "Prime Parts, PrimeParts",   "555 Manufacturing Dr, Detroit, MI",     "TAX-PP-005",     "HIGH",   now.isoformat()),
    ]
    cursor.executemany(
        "INSERT INTO vendor_master (vendor_code, vendor_name, alternate_names, address, tax_id, risk_tier, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        vendors,
    )

    # ── PO-001: Perfect match ──────────────────────────────
    po_items = [
        ("PO-001", "Acme Corp", "Laptop Dell Latitude 5540",   50.0,  1200.00, 60000.00, "ACTIVE", (now - timedelta(days=30)).isoformat()),
        ("PO-001", "Acme Corp", "Wireless Mouse Logitech MX",  50.0,    45.00,  2250.00, "ACTIVE", (now - timedelta(days=30)).isoformat()),
    ]
    gr_items = [
        ("GR-001", "PO-001", "Laptop Dell Latitude 5540",   50.0, (now - timedelta(days=15)).strftime("%Y-%m-%d"), "ACCEPTED"),
        ("GR-002", "PO-001", "Wireless Mouse Logitech MX",  50.0, (now - timedelta(days=15)).strftime("%Y-%m-%d"), "ACCEPTED"),
    ]

    # ── PO-002: Partial receipt (Ordered 100, Received 50) ─
    po_items += [
        ("PO-002", "TechSupply Inc", "Server Rack Unit 42U",  100.0,   50.00, 5000.00, "ACTIVE", (now - timedelta(days=20)).isoformat()),
    ]
    gr_items += [
        ("GR-003", "PO-002", "Server Rack Unit 42U", 50.0, (now - timedelta(days=10)).strftime("%Y-%m-%d"), "ACCEPTED"),
    ]

    # ── PO-003: Vendor name typo ───────────────────────────
    po_items += [
        ("PO-003", "GlobalTech India", "Cloud Hosting Annual License", 1.0, 25000.00, 25000.00, "ACTIVE", (now - timedelta(days=45)).isoformat()),
    ]
    gr_items += [
        ("GR-004", "PO-003", "Cloud Hosting Annual License", 1.0, (now - timedelta(days=5)).strftime("%Y-%m-%d"), "ACCEPTED"),
    ]

    # ── PO-004: Price mismatch (Invoice $52 vs PO $50) ─────
    po_items += [
        ("PO-004", "NexGen Solutions", "Network Switch 48-Port", 20.0, 50.00, 1000.00, "ACTIVE", (now - timedelta(days=25)).isoformat()),
    ]
    gr_items += [
        ("GR-005", "PO-004", "Network Switch 48-Port", 20.0, (now - timedelta(days=12)).strftime("%Y-%m-%d"), "ACCEPTED"),
    ]

    # ── PO-005: Multi-line with mixed results ──────────────
    po_items += [
        ("PO-005", "PrimeParts Ltd", "Hydraulic Pump Assembly",  10.0,  500.00, 5000.00, "ACTIVE", (now - timedelta(days=35)).isoformat()),
        ("PO-005", "PrimeParts Ltd", "Pressure Gauge Module",    25.0,   80.00, 2000.00, "ACTIVE", (now - timedelta(days=35)).isoformat()),
        ("PO-005", "PrimeParts Ltd", "Steel Mounting Bracket",   100.0,  12.00, 1200.00, "ACTIVE", (now - timedelta(days=35)).isoformat()),
    ]
    gr_items += [
        ("GR-006", "PO-005", "Hydraulic Pump Assembly",  10.0, (now - timedelta(days=20)).strftime("%Y-%m-%d"), "ACCEPTED"),
        ("GR-007", "PO-005", "Pressure Gauge Module",    15.0, (now - timedelta(days=20)).strftime("%Y-%m-%d"), "ACCEPTED"),  # Only 15 of 25 received
        ("GR-008", "PO-005", "Steel Mounting Bracket",   100.0, (now - timedelta(days=20)).strftime("%Y-%m-%d"), "ACCEPTED"),
    ]

    # ── PO-006: Used for duplicate invoice testing ─────────
    po_items += [
        ("PO-006", "Acme Corp", "Office Chair Ergonomic Pro", 30.0, 350.00, 10500.00, "ACTIVE", (now - timedelta(days=40)).isoformat()),
    ]
    gr_items += [
        ("GR-009", "PO-006", "Office Chair Ergonomic Pro", 30.0, (now - timedelta(days=18)).strftime("%Y-%m-%d"), "ACCEPTED"),
    ]

    # Insert all PO data
    cursor.executemany(
        "INSERT INTO po_master (po_number, vendor_name, item_desc, qty, unit_price, total_value, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        po_items,
    )

    # Insert all GR data
    cursor.executemany(
        "INSERT INTO gr_records (gr_number, po_number, item_desc, received_qty, receipt_date, quality_status) VALUES (?, ?, ?, ?, ?, ?)",
        gr_items,
    )

    # ── Seed a previous audit for duplicate detection ──────
    past_audit = [
        (
            "past_invoice_po006.txt", "PO-006", "Acme Corp", 10500.00,
            "AUTO_APPROVED", 0.92, 0, "",
            '{"summary": "APPROVED — 0 variance(s) detected."}',
            (now - timedelta(days=7)).isoformat(),
        ),
    ]
    cursor.executemany(
        "INSERT INTO invoice_history (invoice_file, po_number, vendor_name, invoice_total, status, confidence, total_variances, flags, audit_report, processed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        past_audit,
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
    print("✅ Tables created: po_master, gr_records, vendor_master, invoice_history")

    seed_data(conn)

    # Verification
    cursor = conn.cursor()
    po_count = cursor.execute("SELECT COUNT(*) FROM po_master").fetchone()[0]
    gr_count = cursor.execute("SELECT COUNT(*) FROM gr_records").fetchone()[0]
    vendor_count = cursor.execute("SELECT COUNT(*) FROM vendor_master").fetchone()[0]
    hist_count = cursor.execute("SELECT COUNT(*) FROM invoice_history").fetchone()[0]
    print(f"✅ Seeded: {po_count} PO items, {gr_count} GR records, {vendor_count} vendors, {hist_count} historical audits")

    # Print summary
    print("\n📋 PO Master Summary:")
    for row in cursor.execute("SELECT po_number, vendor_name, item_desc, qty, unit_price FROM po_master"):
        print(f"   {row[0]} | {row[1]:20s} | {row[2]:35s} | Qty: {row[3]:>6.0f} | Price: ${row[4]:>10.2f}")

    print("\n📋 GR Records Summary:")
    for row in cursor.execute("SELECT gr_number, po_number, item_desc, received_qty, quality_status FROM gr_records"):
        print(f"   {row[0]} | {row[1]} | {row[2]:35s} | Received: {row[3]:>6.0f} | {row[4]}")

    print("\n📋 Vendor Master:")
    for row in cursor.execute("SELECT vendor_code, vendor_name, risk_tier, tax_id FROM vendor_master"):
        print(f"   {row[0]} | {row[1]:20s} | Risk: {row[2]:6s} | Tax ID: {row[3]}")

    conn.close()
    print("\n🚀 Database initialization complete!")


if __name__ == "__main__":
    main()
