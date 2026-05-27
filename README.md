# Form 13F AI Agent

> **Ask questions about institutional investor holdings in natural language**

A production-ready AI agent that transforms complex SEC Form 13F institutional holdings data into an interactive, conversational interface powered by Claude 3.5 Sonnet.

<div align="center">

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Railway-8b5cf6?style=for-the-badge&logo=railway)](https://streamlit-ui-production-2269.up.railway.app/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql)](https://www.postgresql.org/)

**[🚀 Try Live Demo](https://streamlit-ui-production-2269.up.railway.app/) • [📖 Documentation](docs/) • [🐛 Report Issue](https://github.com/leokeechye/form13f_aiagent/issues)**

</div>

## ✨ What Can You Do?

Ask questions about institutional investor holdings in plain English and get instant, accurate answers backed by SQL-powered data analysis:

**13F Holdings (SQL):**
- 💰 **"How many AAPL shares did Berkshire Hathaway hold in Q4 2024?"**
- 📊 **"What were BlackRock's top 5 holdings by value?"**
- 🔍 **"Show me all managers who held more than 10M shares of TSLA"**
- 📈 **"What was the total value of Vanguard's portfolio in Q3 2024?"**

**10-K Annual Reports (Semantic Search):**
- 🤖 **"What are Apple's main risk factors related to supply chain?"**
- 📉 **"Find companies mentioning recession risks in their 10-K filings"**
- 🏢 **"What does Microsoft say about competition in cloud services?"**

## 🎯 Key Features

- **🗣️ Natural Language Interface** - Ask questions like you're talking to an analyst
- **🔍 SQL-First Architecture** - Generates precise SQL queries for structured data (90% of queries)
- **🧠 RAG Semantic Search** - Search filing commentary and disclosures (10% of queries)
- **📊 Interactive Visualizations** - Portfolio composition, ownership analysis, top movers
- **🔒 Enterprise Security** - Multi-layer SQL validation, authentication, rate limiting
- **🚀 Production Ready** - Deployed on Railway (API + Streamlit UI, two services)
- **📱 Multi-Modal Access** - REST API, Python SDK, and web interface

## 🏗️ Architecture

```
User Query (Natural Language)
         ↓
Claude 3.5 Sonnet Agent (with tool use)
         ↓
    ┌────┴────┐
    ↓         ↓
SQL Tool   RAG Tool
    ↓         ↓
PostgreSQL  Qdrant
(13F data)  (10-K text)
    ↓         ↓
    └────┬────┘
         ↓
Claude Formats Natural Language Answer
```

**Key Components:**
- **Data Ingestion**: Parse 13F-HR XML filings + 10-K annual reports from SEC EDGAR
- **PostgreSQL Database**: Structured storage of holdings and metadata
- **Qdrant Vector DB**: Semantic search over 10-K filing text (risk factors, MD&A)
- **SQL Query Tool**: Claude generates safe, validated SQL queries
- **RAG Search Tool**: Claude searches 10-K sections by meaning
- **Agent**: Orchestrates tools based on query type (quantitative vs qualitative)
- **API**: FastAPI backend with REST endpoints and analytics
- **UI**: Streamlit multi-tab interface with interactive visualizations

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| LLM Provider | LiteLLM (100+ providers) |
| LLM | Claude 3.5 Sonnet (default) |
| Database | PostgreSQL 16+ (Supabase) |
| Vector Database | Qdrant Cloud (semantic search) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| API Framework | FastAPI |
| UI | Streamlit |
| Visualizations | Plotly |
| ORM | SQLAlchemy 2.0 |
| HTTP Client | httpx |
| Testing | pytest |
| Package Manager | uv (10x faster than pip) |
| Deployment | Railway.app — two services: API + Streamlit UI |
| Containerization | Docker |

## 📋 Implementation Phases

| Phase | Description | Duration | Status |
|-------|-------------|----------|--------|
| **Phase 1** | Data Ingestion & Parsing | 2-3 days | ✅ Complete |
| **Phase 2** | PostgreSQL Schema & Loading | 2-3 days | ✅ Complete |
| **Phase 3** | SQL Query Tool | 3-4 days | ✅ Complete |
| **Phase 4** | Agent Orchestration | 2-3 days | ✅ Complete |
| **Phase 5** | FastAPI Backend + Analytics | 2-3 days | ✅ Complete |
| **Phase 6** | Streamlit UI + Visualizations | 2-3 days | ✅ Complete |
| **Phase 7** | Authentication & Security | 2-3 days | ✅ Complete |
| **Phase 8** | RAG/Semantic Search | 3-4 days | ✅ Complete |

**Timeline**: 2-3 weeks to working prototype with SQL queries

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Docker and Docker Compose
- Anthropic API key (for Claude)

### Installation (Docker - Recommended)

1. **Clone repository**
```bash
git clone https://github.com/yourusername/form13f_aiagent.git
cd form13f_aiagent
```

2. **Add your 13F XML files**
```bash
# Place your Form 13F XML files in data/raw/
# See data/raw/README.md for details
cp /path/to/your/filings/*.xml data/raw/
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your Anthropic API key and DB password
```

4. **Start services with Docker**
```bash
docker-compose up -d
```

5. **Run migrations**
```bash
docker-compose exec api alembic upgrade head
```

6. **Ingest 13F data**
```bash
docker-compose exec api python -m src.ingestion.ingest --folder /app/data/raw
```

7. **Access the application**
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Streamlit UI: http://localhost:8501

### Installation (Local Development with uv)

1. **Clone repository**
```bash
git clone https://github.com/leokeechye/form13f_aiagent.git
cd form13f_aiagent
```

2. **Install dependencies with uv** (10x faster than pip)
```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv sync --all-extras
```

3. **Start PostgreSQL**
```bash
docker-compose up -d postgres
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your Anthropic API key and DB password
```

5. **Run migrations**
```bash
alembic upgrade head
```

6. **Ingest 13F data**
```bash
python -m src.ingestion.ingest --folder data/raw
```

7. **Start API locally**
```bash
uvicorn src.api.main:app --reload
```

## 🚂 Deployment (Railway)

Deploy to Railway.app in 3 steps:

1. **Push to GitHub**
```bash
git push
```

2. **Connect to Railway**
- Go to https://railway.app/new
- Select "Deploy from GitHub repo"
- Choose `leokeechye/form13f_aiagent`

3. **Add Environment Variables**
```bash
DATABASE_URL=postgresql://postgres:...@db...supabase.co:5432/postgres
ANTHROPIC_API_KEY=sk-ant-your-key-here
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
```

**Done!** The API is live at **https://form13faiagent-production.up.railway.app** (`/docs` for the OpenAPI UI).

See [docs/RAILWAY_DEPLOYMENT.md](docs/RAILWAY_DEPLOYMENT.md) for detailed guide.

## 🖥️ Streamlit UI Deployment

The production UI runs as a **second Railway service** (`Dockerfile.streamlit`) pointed at the API:

1. **Add a new service** in the same Railway project from the same GitHub repo.
2. **Set the Dockerfile** to `Dockerfile.streamlit` (Settings → Build).
3. **Configure Environment Variables**:
```bash
API_BASE_URL=https://form13faiagent-production.up.railway.app
```

**Production UI**: [https://streamlit-ui-production-2269.up.railway.app/](https://streamlit-ui-production-2269.up.railway.app/)

> **Alternative (free):** the UI can also be hosted on [Streamlit Cloud](https://share.streamlit.io) — set the main file to `src/ui/app.py` and the same `API_BASE_URL`. Streamlit Cloud uses `requirements.txt`, which is included in the repo.

## 📁 Project Structure

```
form13f_aiagent/
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── .env.example
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── IMPLEMENTATION_PLAN.md
│   ├── SQL_SCHEMA.md
│   └── DECISIONS.md
│
├── data/
│   ├── raw/              # 13F XML filings (committed to git)
│   ├── processed/        # Parsed data (not tracked)
│   └── cache/            # Temporary cache (not tracked)
│
├── alembic/              # Database migrations
│   └── versions/
│
├── src/
│   ├── agent/            # Claude agent orchestrator
│   ├── api/              # FastAPI backend
│   ├── db/               # Database layer (SQLAlchemy)
│   ├── ingestion/        # SEC data ingestion (13F + 10-K)
│   ├── models/           # Pydantic data models
│   ├── rag/              # RAG components (embeddings, vector store)
│   ├── tools/            # SQL + RAG search tools
│   ├── ui/               # Streamlit interface
│   └── utils/
│
├── scripts/
│   ├── download_filings.py
│   └── populate_db.py
│
└── tests/
    ├── unit/
    └── integration/
```

## 🔑 Key Features

### 1. Natural Language to SQL
Claude converts natural language questions into safe SQL queries:

**Input**: "How many AAPL shares did Berkshire hold in Q4 2024?"

**Generated SQL**:
```sql
SELECT h.shares_or_principal, h.value_thousands, f.period_of_report
FROM holdings h
JOIN filings f ON h.accession_number = f.accession_number
WHERE f.cik = '0001067983'
  AND h.ticker = 'AAPL'
  AND f.period_of_report BETWEEN '2024-10-01' AND '2024-12-31'
LIMIT 1;
```

**Answer**: "Berkshire Hathaway held 916,000,000 shares of Apple Inc (AAPL) valued at $157 billion in Q4 2024."

### 2. SQL Safety & Validation
- Read-only queries (SELECT only)
- Query timeout limits (5 seconds)
- Row limits (max 1000 rows)
- SQL injection prevention
- Schema validation

### 3. Database Schema
```sql
-- Core tables
filings       -- Filing metadata (CIK, manager, date, total value)
holdings      -- Individual positions (CUSIP, ticker, shares, value)
issuers       -- Issuer reference data (CUSIP → ticker mapping)
managers      -- Manager reference data (CIK → name mapping)
```

See `docs/SQL_SCHEMA.md` for complete schema.

### 4. Query Examples

| Question | Complexity | Works? |
|----------|------------|--------|
| "How many AAPL shares did Berkshire hold?" | Simple | ✅ |
| "What were Berkshire's top 5 holdings by value?" | Moderate | ✅ |
| "Which managers held more than $1B in TSLA?" | Complex | ✅ |
| "What was the average portfolio value in Q4 2024?" | Analytics | ✅ |
| "Show me all tech holdings across all managers" | Complex | ✅ |

### 5. Interactive Visualizations
The Streamlit UI includes 4 tabs with interactive Plotly visualizations:

**💬 Chat Tab**
- Natural language query interface
- Real-time SQL generation and execution
- CSV export of query results

**📈 Portfolio Explorer**
- Search and select institutional managers
- Portfolio composition charts (pie/bar)
- Key metrics: total value, concentration, holdings count
- Top holdings breakdown with percentages

**🔍 Security Analysis**
- Institutional ownership analysis by CUSIP/ticker
- Top holders visualization
- Ownership concentration metrics (Herfindahl Index)
- Quarter-over-quarter ownership changes

**🚀 Top Movers**
- Biggest portfolio position increases/decreases
- Color-coded charts (green=increase, red=decrease)
- Filter by time period
- Percentage and dollar value changes

All visualizations are:
- Interactive (hover, zoom, pan)
- Responsive (mobile-friendly)
- Cached for performance (5-minute TTL)

### 6. Analytics API Endpoints
FastAPI provides dedicated analytics endpoints:

- `GET /api/v1/analytics/portfolio/{cik}` - Portfolio composition and top holdings
- `GET /api/v1/analytics/security/{cusip}` - Institutional ownership analysis
- `GET /api/v1/analytics/movers` - Biggest position changes across managers
- `GET /api/v1/managers` - Search and list institutional managers

See API docs at `/docs` for full endpoint documentation.

### 7. RAG/Semantic Search (Phase 8 - Completed)
The system includes semantic search over SEC filing text using Qdrant vector database.

**Form 10-K Annual Reports (Rich Qualitative Data):**
- Item 1: Business descriptions and strategy
- Item 1A: Risk factors and challenges
- Item 7: Management's Discussion & Analysis (MD&A)
- Item 7A: Market risk disclosures

The agent can filter 10-K searches by:
- `filter_cik_company`: Company CIK (e.g., Apple, Microsoft)
- `filter_section`: Specific section (Item 1A, Item 7, etc.)
- `filter_year`: Filing year

**Example 10-K queries:**
- "What are Apple's main supply chain risks?"
- "Find companies mentioning recession concerns in their risk factors"
- "What does Microsoft's MD&A say about cloud growth?"

**Form 13F Holdings Reports (Limited Text):**
13F filings contain only regulatory boilerplate - manager addresses, amendment notices.
They do NOT contain investment strategies or market commentary.
Use SQL queries for 13F holdings analysis instead.

## 📊 Example Usage

### CLI
```bash
# Ask a question
python -m src.agent.cli "How many AAPL shares did Berkshire hold in Q4 2024?"
```

### API
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What were BlackRock'\''s top 5 holdings?"}'
```

### Python
```python
from src.agent.orchestrator import Agent

agent = Agent()
result = agent.query("How many AAPL shares did Berkshire hold?")

print(result.answer)
print(result.sql_query)  # See generated SQL
print(result.raw_data)   # See query results
```

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Required
ANTHROPIC_API_KEY=your_anthropic_key
DB_PASSWORD=your_secure_password

# Optional
LOG_LEVEL=INFO
ENVIRONMENT=development
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run unit tests
pytest tests/unit/

# Run integration tests (requires database)
pytest tests/integration/

# Test SQL generation
pytest tests/unit/test_sql_tool.py -v
```

## 📖 Documentation

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and design decisions
- **[IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)** - 6-phase roadmap
- **[SQL_SCHEMA.md](docs/SQL_SCHEMA.md)** - Database schema and queries
- **[DECISIONS.md](docs/DECISIONS.md)** - Why SQL-first, why Claude, etc.

## 📈 Performance

- **Query Latency**: < 2 seconds end-to-end
- **SQL Generation**: < 1 second
- **Database Queries**: < 100ms (with proper indexes)
- **Supported Scale**: 100,000+ holdings, 10,000+ filings
- **Concurrent Users**: 50+

## 🤝 Future Enhancements

### Phase 9: Advanced Features
- Real-time data updates (SEC RSS feed)
- Multi-manager comparisons
- Time-series analysis
- Export to Excel/CSV
- Slack/Teams integration

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 📧 Contact

For questions or feedback, please open an issue.

---

**Status**: ✅ Phases 1-8 Complete - Production Ready
**Architecture**: SQL-First + RAG Semantic Search
**Live Demo**: [Streamlit App](https://streamlit-ui-production-2269.up.railway.app/)

---

Made with Claude 3.5 Sonnet | MIT License
