<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/LangGraph-Stateful_AI-FF6F00?style=for-the-badge&logo=chainlink&logoColor=white" />
  <img src="https://img.shields.io/badge/Streamlit-Enterprise_UI-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" />
  <img src="https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=for-the-badge&logo=openai&logoColor=white" />
</p>

# 🔍 S2P Audit Core

**Production-grade, AI-powered Three-Way Match audit engine for enterprise procurement.**

S2P Audit Core automates the most critical control point in Source-to-Pay (S2P) workflows: the **Three-Way Match** — verifying that every invoice aligns with its Purchase Order and Goods Receipt before payment is authorized.

> Traditional ERP systems rely on rigid, rule-based matching that fails on messy real-world data.  
> This system combines **LLM-powered document understanding** with **deterministic financial auditing** — the AI reads, but Python does the math.

---

## 🎯 Why This Exists

In enterprise procurement, **duplicate and fraudulent payments** cost organizations an estimated 1-2% of total revenue annually. Three-Way Matching is the primary control — but it's still largely manual in most organizations:

| Challenge | How S2P Audit Core Solves It |
|---|---|
| Invoices arrive as unstructured text/OCR | GPT-4o extracts structured data with confidence scoring |
| Vendor names have typos across systems | Fuzzy matching with configurable similarity thresholds |
| Partial shipments create quantity mismatches | GR-aware quantity validation (cannot bill for unreceived goods) |
| Price discrepancies need tolerance bands | Configurable tolerance (default: 1%) with line-level variance reporting |
| Auditors need explainability, not black boxes | Every decision is deterministic Python — fully auditable |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Streamlit Enterprise UI                      │
│         (Upload · Real-time Status · Audit Dashboard)           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    LangGraph Workflow Engine                     │
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────────┐   │
│  │ Extract  │───▶│  Fetch ERP   │───▶│ Deterministic Audit │   │
│  │ (GPT-4o) │    │ + Fuzzy Match│    │  (Pure Python)      │   │
│  └──────────┘    └──────────────┘    └──────────┬──────────┘   │
│                                                  │              │
│                                    ┌─────────────┴───────────┐  │
│                                    │  Conditional Routing     │  │
│                                    │  AUTO_APPROVED │ REVIEW  │  │
│                                    └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    SQLite Mock ERP Layer                         │
│              (PO Master · Goods Receipts · Seed Data)           │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **AI Reads, Python Audits** — The LLM's *only* job is extracting structured data from unstructured text. All financial logic (quantity checks, price tolerance, variance reporting) runs in deterministic Python. No LLM hallucination in the audit path.

2. **Stateful Execution via LangGraph** — Not a simple chain. The workflow is a compiled `StateGraph` with typed state, explicit edges, and conditional routing. Every node receives and returns a well-defined `TypedDict` state.

3. **Fail-Safe Routing** — Any variance (quantity, price, vendor mismatch) OR low extraction confidence (< 85%) automatically routes to `MANUAL_REVIEW`. The system errs on the side of caution.

4. **Enterprise-Ready Patterns** — Pydantic v2 validation on all LLM outputs, fuzzy matching for real-world vendor name inconsistencies, line-level audit trails, structured error handling.

---

## 📁 Project Structure

```
s2p-ai-audit/
├── README.md                  # You are here
├── requirements.txt           # Production dependencies
├── .env                       # API key configuration
├── init_db.py                 # Mock ERP database seeder
├── app.py                     # Streamlit enterprise dashboard
├── erp_system.db              # SQLite database (generated)
└── src/
    ├── __init__.py
    ├── models.py              # Pydantic v2 schemas (InvoiceSchema, LineItem)
    ├── state.py               # LangGraph TypedDict state definition
    ├── tools.py               # SQLite queries + fuzzy vendor matching
    ├── nodes.py               # LangGraph node functions (extract, fetch, audit)
    └── graph.py               # StateGraph assembly + conditional routing
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

### Test It

Create a file called `invoice_test.txt`:

```
Invoice from TechSupply Inc for PO-002.
Billing for 100 units of Server Rack Unit 42U at $50.00 each.
Subtotal: $5,000.00
Tax: $0.00
Total: $5,000.00
```

Upload it through the UI. The system will:
1. ✅ Extract the invoice data via GPT-4o
2. ✅ Fetch PO-002 from the ERP (ordered 100 units)
3. ❌ **Flag it** — only 50 units were received (GR), but 100 are being billed
4. → Route to **MANUAL REVIEW**

---

## 🔬 How the Three-Way Match Works

### The Three Documents

| Document | Source | Purpose |
|---|---|---|
| **Purchase Order (PO)** | Buyer's ERP | "We agreed to buy X items at Y price" |
| **Goods Receipt (GR)** | Warehouse/Logistics | "We physically received Z items" |
| **Invoice** | Vendor/Supplier | "Please pay us for N items at M price" |

### Audit Checks (Deterministic)

```python
# Check 1: Quantity Validation
# Cannot bill for items not yet received
assert invoice_qty <= gr_received_qty

# Check 2: Price Tolerance (1% band)
# Unit price must match PO within tolerance
assert abs(invoice_price - po_price) / po_price <= 0.01

# Check 3: Vendor Verification (Fuzzy)
# Handles typos: "TechSupply" vs "Tech Supply Inc"
assert fuzzy_score(invoice_vendor, po_vendor) >= 75
```

### Routing Logic

```
IF    total_variances == 0
  AND confidence_score >= 0.85
  AND vendor_match == True
THEN  → AUTO_APPROVED ✅

ELSE  → MANUAL_REVIEW ⚠️
```

---

## 🧪 Seed Data & Edge Cases

The mock ERP (`init_db.py`) includes carefully designed edge cases:

| PO Number | Scenario | Expected Outcome |
|---|---|---|
| `PO-001` | ✅ Perfect match — quantities and prices align | `AUTO_APPROVED` |
| `PO-002` | ⚠️ Partial receipt — ordered 100, received 50 | `MANUAL_REVIEW` if invoice > 50 units |
| `PO-003` | ⚠️ Vendor name mismatch — typo across systems | Tests fuzzy matching threshold |

---

## 🛠️ Technical Deep Dive

### LangGraph State Machine

The workflow is compiled as a `StateGraph` — not a simple sequential chain. Each node is a pure function that receives typed state and returns a partial update:

```python
class AuditState(TypedDict):
    file_name: str                          # Input filename
    raw_text: str                           # Raw invoice text
    extracted_data: Optional[InvoiceSchema] # LLM extraction output
    erp_context: Optional[dict]             # PO + GR data from ERP
    audit_report: Optional[dict]            # Line-level audit results
    status: str                             # PENDING → APPROVED | MANUAL_REVIEW
```

### Structured LLM Output

Instead of parsing free-text LLM responses, the system uses LangChain's `.with_structured_output()` to force GPT-4o to return a validated Pydantic v2 model:

```python
structured_llm = ChatOpenAI(model="gpt-4o", temperature=0)
    .with_structured_output(InvoiceSchema)

# Returns a validated InvoiceSchema instance — not a string
result: InvoiceSchema = structured_llm.invoke(messages)
```

### Fuzzy Vendor Matching

Real-world vendor names are inconsistent across documents. The system uses token-sort ratio matching, which normalizes word order and casing before comparing:

```python
fuzzy_match("TechSupply Inc", "Tech Supply")  # → (True, 82)
fuzzy_match("Acme Corp", "Acme Corporation")  # → (True, 87)
fuzzy_match("Vendor A", "Totally Different")   # → (False, 23)
```

---

## 📊 Streamlit Dashboard

The enterprise UI provides:

- **Sidebar Console** — Real-time database connection status, ERP data viewer
- **File Upload** — Drag-and-drop `.txt` files (simulating OCR output)
- **Live Execution Status** — Step-by-step progress of the LangGraph workflow
- **Split-View Results**:
  - Left panel: Extracted invoice data with confidence metrics
  - Right panel: Audit report with color-coded variance indicators (🟢 PASS / 🔴 FAIL)
- **Final Verdict** — Large status card: `AUTO_APPROVED` or `MANUAL_REVIEW`

---

## 🗺️ Roadmap

- [ ] **PDF/Image Invoice Support** — OCR integration (Tesseract / Azure Document Intelligence)
- [ ] **Multi-line PO Matching** — Fuzzy item description matching across line items
- [ ] **Batch Processing** — Upload multiple invoices with aggregate reporting
- [ ] **PostgreSQL Backend** — Replace SQLite for production deployments
- [ ] **Audit Trail Persistence** — Store all audit decisions with timestamps
- [ ] **Role-Based Access** — Reviewer vs. Approver workflows
- [ ] **Webhook Integration** — Notify downstream systems on auto-approval

---

## 🧰 Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **AI Orchestration** | LangGraph | Stateful workflow engine with conditional routing |
| **LLM** | OpenAI GPT-4o | Structured invoice data extraction |
| **Validation** | Pydantic v2 | Schema enforcement on LLM outputs |
| **Database** | SQLite + pandas | Mock ERP data layer |
| **Fuzzy Matching** | thefuzz (Levenshtein) | Vendor name normalization |
| **UI** | Streamlit | Enterprise dashboard with Carbon design language |
| **Config** | python-dotenv | Environment-based configuration |

---

## 📄 License

MIT

---

<p align="center">
  <sub>Built with ⚡ LangGraph · 🧠 GPT-4o · 🐍 Python</sub>
</p>
