<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/LangGraph-Stateful_AI-FF6F00?style=for-the-badge&logo=chainlink&logoColor=white" />
  <img src="https://img.shields.io/badge/Streamlit-Enterprise_UI-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=for-the-badge&logo=openai&logoColor=white" />
  <img src="https://img.shields.io/badge/Tests-26%20Passing-10b981?style=for-the-badge" />
</p>

# 🔍 S2P AI Audit

**Production-grade, AI-powered Three-Way Match audit engine for enterprise procurement.**

S2P AI Audit automates the most critical control point in Source-to-Pay (S2P) workflows: the **Three-Way Match** — verifying that every invoice aligns with its Purchase Order and Goods Receipt before payment is authorized.

> Traditional ERP systems rely on rigid, rule-based matching that fails on messy real-world data.  
> This system combines **LLM-powered document understanding** with **deterministic financial auditing** — the AI reads, but Python does the math.

---

## 🎯 Why This Exists

In enterprise procurement, **duplicate and fraudulent payments** cost organizations an estimated 1-2% of total revenue annually. Three-Way Matching is the primary control — but it's still largely manual in most organizations:

| Challenge | How S2P AI Audit Solves It |
|---|---|
| Invoices arrive as unstructured text/OCR | GPT-4o extracts structured data with confidence scoring |
| Vendor names have typos across systems | Fuzzy matching with configurable similarity thresholds |
| Partial shipments create quantity mismatches | GR-aware quantity validation (cannot bill for unreceived goods) |
| Price discrepancies need tolerance bands | Configurable tolerance (default: 1%) with line-level variance reporting |
| Duplicate invoices slip through | Automatic duplicate detection against audit history |
| Auditors need explainability, not black boxes | Every decision is deterministic Python — fully auditable |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                 Multi-Page Streamlit Enterprise UI                    │
│  ┌─────────────┐  ┌──────────────────┐  ┌────────────────────────┐  │
│  │ Audit Engine │  │ Analytics & Trends│  │ ERP Data Manager      │  │
│  └──────┬──────┘  └──────────────────┘  └────────────────────────┘  │
└─────────┼────────────────────────────────────────────────────────────┘
          │
┌─────────▼────────────────────────────────────────────────────────────┐
│                  LangGraph Workflow Engine                             │
│                                                                       │
│  ┌──────────┐    ┌────────────────┐    ┌──────────────────────────┐  │
│  │ Extract  │───▶│  Fetch ERP +   │───▶│  Deterministic Audit     │  │
│  │ (GPT-4o) │    │  Vendor Match  │    │  + Duplicate Detection   │  │
│  │ ↓ fallback    │  + Vendor Master│    │  + History Persistence   │  │
│  │ (GPT-4o-mini) └────────────────┘    └──────────┬───────────────┘  │
│  └──────────┘                                     │                   │
│                                      ┌────────────┴──────────────┐   │
│                                      │   Conditional Routing      │   │
│                                      │  AUTO_APPROVED │ REVIEW    │   │
│                                      └───────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
          │
┌─────────▼────────────────────────────────────────────────────────────┐
│                     SQLite ERP Layer                                   │
│        PO Master · Goods Receipts · Vendor Master · Audit History     │
└──────────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **AI Reads, Python Audits** — The LLM's *only* job is extracting structured data from unstructured text. All financial logic runs in deterministic Python. No LLM hallucination in the audit path.

2. **Stateful Execution via LangGraph** — Not a simple chain. The workflow is a compiled `StateGraph` with typed state, conditional edges, and error-aware routing with LLM fallback.

3. **Five Audit Checks** — Quantity vs GR, price tolerance, vendor verification, duplicate detection, and vendor risk tier assessment.

4. **Fail-Safe Routing** — Any variance OR low confidence (< 85%) automatically routes to `MANUAL_REVIEW`. The system errs on the side of caution.

5. **Full Audit Trail** — Every invoice processed is persisted to `invoice_history` for trend analysis and duplicate detection.

---

## 📁 Project Structure

```
s2p-ai-audit/
├── README.md
├── requirements.txt
├── .env                        # API key config (gitignored)
├── init_db.py                  # Mock ERP database seeder (6 POs, 5 vendors)
├── app.py                      # Multi-page Streamlit dashboard
├── Dockerfile                  # Multi-stage production build
├── docker-compose.yml          # One-command deployment
├── sample_invoices/            # Pre-made test invoices for each edge case
│   ├── 01_perfect_match.txt
│   ├── 02_qty_mismatch.txt
│   ├── 03_vendor_typo.txt
│   ├── 04_price_mismatch.txt
│   ├── 05_multiline_mixed.txt
│   └── 06_duplicate.txt
├── src/
│   ├── __init__.py
│   ├── models.py               # Pydantic v2 schemas (InvoiceSchema, LineItem)
│   ├── state.py                # LangGraph TypedDict state definition
│   ├── tools.py                # SQLite queries, fuzzy matching, duplicate detection
│   ├── nodes.py                # LangGraph nodes (extract, fetch, audit)
│   ├── graph.py                # StateGraph assembly with error-aware routing
│   └── analytics.py            # Audit stats, variance trends, vendor risk scoring
├── tests/
│   ├── test_tools.py           # 18 unit tests for queries, matching, persistence
│   └── test_nodes.py           # 8 integration tests for audit logic
└── .github/workflows/ci.yml   # GitHub Actions CI (lint, test, smoke test)
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- An OpenAI API key with access to `gpt-4o`

### Setup

```bash
# Clone and enter the project
git clone <repo-url> && cd s2p-ai-audit

# Create virtual environment
python -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure API key
echo "OPENAI_API_KEY=sk-your-key-here" > .env

# Initialize the mock ERP database
python init_db.py
```

### Run

```bash
streamlit run app.py
```

### Docker

```bash
docker-compose up --build
# Open http://localhost:8501
```

### Test

```bash
pytest tests/ -v
# 26 tests, all passing
```

---

## 🖥️ Dashboard Pages

### Page 1: Audit Engine
- **Upload** invoice text files or **generate sample invoices** from 6 pre-built edge cases
- Real-time step-by-step execution with `st.status`
- Two-column results: extracted data (left) + color-coded audit report (right)
- Big status card: `AUTO_APPROVED` ✅ or `MANUAL_REVIEW` ⚠️

### Page 2: Analytics
- Summary metrics: total audits, approval rate, avg confidence, total variances
- Filterable audit history table with CSV export
- Common flags bar chart
- Vendor risk assessment scores

### Page 3: ERP Data Manager
- Browse PO Master, Goods Receipts, Vendor Registry
- PO fulfillment tracking with progress bars
- Tabbed interface for data exploration

---

## 🔬 How the Three-Way Match Works

### The Three Documents

| Document | Source | Purpose |
|---|---|---|
| **Purchase Order (PO)** | Buyer's ERP | "We agreed to buy X items at Y price" |
| **Goods Receipt (GR)** | Warehouse/Logistics | "We physically received Z items" |
| **Invoice** | Vendor/Supplier | "Please pay us for N items at M price" |

### Five Audit Checks (All Deterministic)

```python
# Check 1: Quantity — cannot bill for unreceived items
assert invoice_qty <= gr_received_qty

# Check 2: Price — must match PO within 1% tolerance
assert abs(invoice_price - po_price) / po_price <= 0.01

# Check 3: Vendor — fuzzy match handles typos
assert fuzzy_score(invoice_vendor, po_vendor) >= 75

# Check 4: Duplicate — same PO + vendor + amount already billed?
assert not is_duplicate_invoice(po_number, vendor, total)

# Check 5: Vendor Risk — flag high-risk vendors
if vendor_risk_tier == "HIGH": add_flag("HIGH_RISK_VENDOR")
```

### Routing Logic

```
IF    total_variances == 0
  AND confidence_score >= 0.85
  AND vendor_match == True
  AND no_duplicate == True
THEN  → AUTO_APPROVED ✅

ELSE  → MANUAL_REVIEW ⚠️
```

---

## 🧪 Edge Cases & Sample Invoices

| File | PO | Scenario | Expected |
|---|---|---|---|
| `01_perfect_match.txt` | PO-001 | All quantities and prices match | `AUTO_APPROVED` |
| `02_qty_mismatch.txt` | PO-002 | Bills 100 units, only 50 received | `MANUAL_REVIEW` |
| `03_vendor_typo.txt` | PO-003 | "GlobalTech Pvt Ltd" vs "GlobalTech India" | `MANUAL_REVIEW` |
| `04_price_mismatch.txt` | PO-004 | $52 invoice vs $50 PO (4% deviation) | `MANUAL_REVIEW` |
| `05_multiline_mixed.txt` | PO-005 | 3 items: 2 pass, 1 fails (qty) | `MANUAL_REVIEW` |
| `06_duplicate.txt` | PO-006 | Same PO+vendor+amount already processed | `MANUAL_REVIEW` |

---

## 🛠️ Technical Deep Dive

### LangGraph State Machine

```python
class AuditState(TypedDict):
    file_name: str                          # Input filename
    raw_text: str                           # Raw invoice text
    extracted_data: Optional[InvoiceSchema] # LLM extraction (Pydantic v2)
    erp_context: Optional[dict]             # PO + GR + Vendor Master data
    audit_report: Optional[dict]            # Line-level audit with variances
    status: str                             # PENDING → APPROVED | MANUAL_REVIEW
```

### Error-Resilient Graph

```python
# Primary: GPT-4o → Fallback: GPT-4o-mini
# On complete failure: error_handler route → structured error report
extract → [success] → fetch_erp → deterministic_audit → END
extract → [failure] → deterministic_audit (error report) → END
```

### Structured LLM Output (No String Parsing)

```python
structured_llm = ChatOpenAI(model="gpt-4o", temperature=0)
    .with_structured_output(InvoiceSchema)
result: InvoiceSchema = structured_llm.invoke(messages)  # Validated Pydantic
```

---

## 🗺️ Roadmap

- [ ] **PDF/Image Invoice Support** — OCR integration (Tesseract / Azure Document Intelligence)
- [ ] **Multi-line PO Matching** — Advanced fuzzy matching across item descriptions
- [ ] **Real-time WebSocket Updates** — Live audit status streaming
- [ ] **PostgreSQL Backend** — Replace SQLite for team deployments
- [ ] **Role-Based Access** — Reviewer vs. Approver workflows
- [ ] **Webhook Integration** — Notify downstream systems on auto-approval
- [ ] **LangSmith Observability** — Full trace of every LLM call and graph execution

---

## 🧰 Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **AI Orchestration** | LangGraph | Stateful workflow with conditional routing |
| **LLM** | OpenAI GPT-4o | Structured invoice extraction (+ GPT-4o-mini fallback) |
| **Validation** | Pydantic v2 | Schema enforcement on LLM outputs |
| **Database** | SQLite + pandas | Mock ERP with 4 tables |
| **Fuzzy Matching** | thefuzz (Levenshtein) | Vendor + item description normalization |
| **UI** | Streamlit | Multi-page enterprise dashboard |
| **CI/CD** | GitHub Actions | Automated testing on push |
| **Containerization** | Docker | Production-ready deployment |

---

## 📄 License

MIT

---

<p align="center">
  <sub>Built with ⚡ LangGraph · 🧠 GPT-4o · 🐍 Python · 26 tests passing</sub>
</p>
