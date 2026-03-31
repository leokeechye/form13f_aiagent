"""
FastAPI Application - Form 13F AI Agent

Main entry point for the REST API.
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import time
import logging
from typing import AsyncGenerator
from pathlib import Path

from .dependencies import get_database_url
from .schemas import ErrorResponse, HealthResponse, DatabaseStatsResponse
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Version
VERSION = "0.1.0"

# Global database engine for health checks (reused to avoid connection exhaustion)
_health_check_engine = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan events.

    Runs on startup and shutdown.
    """
    # Startup
    logger.info("=" * 60)
    logger.info(f"Form 13F AI Agent API v{VERSION}")
    logger.info("=" * 60)

    # Test database connection
    try:
        database_url = get_database_url()
        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Database connection successful")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")

    # Test LLM configuration
    try:
        import os
        llm_provider = os.getenv("LLM_PROVIDER", "anthropic")
        llm_model = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
        api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")

        if api_key and api_key != "sk-ant-your-key-here":
            logger.info(f"✅ LLM configured: {llm_provider}/{llm_model}")
        else:
            logger.warning("⚠️  LLM API key not configured")
    except Exception as e:
        logger.warning(f"⚠️  LLM configuration issue: {e}")

    logger.info(f"🚀 API started on port {os.getenv('PORT', '8000')}")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("Shutting down API...")


# Create FastAPI app
app = FastAPI(
    title="Form 13F AI Agent API",
    description="""
    Natural language interface to SEC Form 13F institutional holdings data.

    Ask questions in plain English and get accurate answers powered by Claude 3.5 Sonnet.

    ## Features
    - Natural language queries
    - SQL generation and execution
    - Form 13F data from institutional investors
    - RESTful endpoints for direct data access

    ## Example Questions
    - "How many Apple shares did Berkshire Hathaway hold in Q4 2024?"
    - "What are the top 5 managers by portfolio value?"
    - "Who holds the most Tesla stock?"
    """,
    version=VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests"""
    start_time = time.time()

    # Log request
    logger.info(f"→ {request.method} {request.url.path}")

    # Process request
    response = await call_next(request)

    # Log response
    duration = (time.time() - start_time) * 1000
    logger.info(f"← {response.status_code} ({duration:.0f}ms)")

    return response


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    errors = exc.errors()
    logger.warning(f"Validation error: {errors}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            detail=f"Validation error: {errors[0]['msg']}",
            error_code="VALIDATION_ERROR"
        ).model_dump(mode='json')
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions"""
    logger.error(f"ValueError: {exc}")

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            detail=str(exc),
            error_code="VALUE_ERROR"
        ).model_dump(mode='json')
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            detail="Internal server error. Please try again later.",
            error_code="INTERNAL_ERROR"
        ).model_dump(mode='json')
    )


# Root endpoint - serve web UI
@app.get("/", tags=["Root"])
async def root():
    """Serve the web UI"""
    ui_path = Path(__file__).parent.parent / "ui" / "templates" / "index.html"
    if ui_path.exists():
        return FileResponse(ui_path)
    else:
        # Fallback to API info if UI not found
        return {
            "name": "Form 13F AI Agent API",
            "version": VERSION,
            "docs": "/docs",
            "health": "/health",
            "query": "/api/v1/query"
        }


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns service status and connectivity.
    """
    global _health_check_engine

    # Check database - reuse cached engine to avoid connection exhaustion
    database_status = "disconnected"
    try:
        if _health_check_engine is None:
            database_url = get_database_url()
            _health_check_engine = create_engine(
                database_url,
                pool_size=1,
                max_overflow=0,
                pool_pre_ping=True
            )

        with _health_check_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception as e:
        logger.error(f"Health check database error: {e}")

    # Check LLM
    llm_status = "not_configured"
    try:
        import os
        api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY")
        if api_key and api_key != "sk-ant-your-key-here":
            llm_status = "configured"
    except Exception:
        pass

    # Always return healthy for Railway healthcheck
    # Even if database is temporarily unavailable, the app is still running
    return HealthResponse(
        status="healthy",
        database=database_status,
        llm=llm_status,
        version=VERSION
    )


# Database stats endpoint
@app.get("/api/v1/stats", response_model=DatabaseStatsResponse, tags=["Statistics"])
async def get_stats():
    """
    Get database statistics.

    Returns counts of managers, filings, holdings, etc.
    """
    global _health_check_engine

    try:
        # Reuse the health check engine to avoid connection pool exhaustion
        if _health_check_engine is None:
            database_url = get_database_url()
            _health_check_engine = create_engine(
                database_url,
                pool_size=1,
                max_overflow=0,
                pool_pre_ping=True
            )

        with _health_check_engine.connect() as conn:
            # Count records
            managers_count = conn.execute(text("SELECT COUNT(*) FROM managers")).scalar()
            issuers_count = conn.execute(text("SELECT COUNT(*) FROM issuers")).scalar()
            filings_count = conn.execute(text("SELECT COUNT(*) FROM filings")).scalar()
            holdings_count = conn.execute(text("SELECT COUNT(*) FROM holdings")).scalar()

            # Get latest quarter
            latest_quarter_result = conn.execute(
                text("SELECT MAX(period_of_report) FROM filings")
            ).scalar()
            latest_quarter = str(latest_quarter_result) if latest_quarter_result else None

            # Get total value
            total_value_result = conn.execute(
                text("SELECT SUM(value) FROM holdings")
            ).scalar()
            total_value = int(total_value_result) if total_value_result else None

        return DatabaseStatsResponse(
            managers_count=managers_count or 0,
            issuers_count=issuers_count or 0,
            filings_count=filings_count or 0,
            holdings_count=holdings_count or 0,
            latest_quarter=latest_quarter,
            total_value=total_value
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise ValueError(f"Failed to get database statistics: {str(e)}")


# Temporary data ingestion - REMOVE AFTER RE-INGESTION
GITHUB_TSV_BASE = (
    "https://media.githubusercontent.com/media/leokeechye/form13f_aiagent/main/data/raw"
)

_ingest_status = {"state": "idle", "detail": "", "stats": {}}


def _run_ingestion_background():
    """Background ingestion worker."""
    import csv
    import io
    import subprocess
    import tempfile
    from datetime import datetime
    from sqlalchemy import text as sa_text
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from src.db.session import SessionLocal
    from src.db.models import Manager, Issuer, Filing, Holding

    global _ingest_status
    _ingest_status = {"state": "running", "detail": "Starting...", "stats": {}}
    stats = {"managers": 0, "issuers": 0, "filings": 0, "holdings": 0}

    def download_tsv(filename):
        url = f"{GITHUB_TSV_BASE}/{filename}"
        logger.info(f"Downloading {filename} from GitHub...")
        _ingest_status["detail"] = f"Downloading {filename}..."
        result = subprocess.run(
            ["curl", "-sL", url], capture_output=True, text=True, timeout=300
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to download {filename}: {result.stderr}")
        logger.info(f"Downloaded {filename} ({len(result.stdout):,} bytes)")
        return result.stdout

    def download_tsv_to_file(filename):
        url = f"{GITHUB_TSV_BASE}/{filename}"
        logger.info(f"Downloading {filename} from GitHub (streaming to disk)...")
        _ingest_status["detail"] = f"Downloading {filename} (large file)..."
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False)
        result = subprocess.run(["curl", "-sL", "-o", tmp.name, url], timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to download {filename}")
        import os as _os
        size = _os.path.getsize(tmp.name)
        logger.info(f"Downloaded {filename} ({size:,} bytes) to {tmp.name}")
        return tmp.name

    try:
        session = SessionLocal()

        _ingest_status["detail"] = "Truncating tables..."
        logger.info("Truncating tables for clean ingestion...")
        session.execute(sa_text("TRUNCATE TABLE holdings CASCADE"))
        session.execute(sa_text("TRUNCATE TABLE filings CASCADE"))
        session.execute(sa_text("TRUNCATE TABLE issuers CASCADE"))
        session.execute(sa_text("TRUNCATE TABLE managers CASCADE"))
        session.commit()

        _ingest_status["detail"] = "Downloading small TSV files..."
        def parse_tsv_string(content):
            rows = {}
            reader = csv.DictReader(io.StringIO(content), delimiter="\t")
            for row in reader:
                rows[row["ACCESSION_NUMBER"]] = row
            return rows

        submissions = parse_tsv_string(download_tsv("SUBMISSION.tsv"))
        coverpages = parse_tsv_string(download_tsv("COVERPAGE.tsv"))
        summaries = parse_tsv_string(download_tsv("SUMMARYPAGE.tsv"))

        def parse_date(date_str):
            return datetime.strptime(date_str, "%d-%b-%Y").date()

        _ingest_status["detail"] = "Inserting managers and filings..."
        managers = {}
        filing_dicts = []

        for acc_num, sub in submissions.items():
            if sub["SUBMISSIONTYPE"] != "13F-HR":
                continue
            cover = coverpages.get(acc_num)
            summary = summaries.get(acc_num)
            if not cover or not summary:
                continue
            try:
                cik = sub["CIK"]
                managers[cik] = cover["FILINGMANAGER_NAME"]
                filing_dicts.append({
                    "accession_number": acc_num,
                    "cik": cik,
                    "filing_date": parse_date(sub["FILING_DATE"]),
                    "period_of_report": parse_date(sub["PERIODOFREPORT"]),
                    "submission_type": sub["SUBMISSIONTYPE"],
                    "report_type": cover["REPORTTYPE"],
                    "total_value": int(summary["TABLEVALUETOTAL"] or 0),
                    "number_of_holdings": int(summary["TABLEENTRYTOTAL"] or 0),
                })
            except (KeyError, ValueError) as e:
                logger.warning(f"Skipping filing {acc_num}: {e}")

        if managers:
            mgr_dicts = [{"cik": cik, "name": name} for cik, name in managers.items()]
            stmt = pg_insert(Manager).values(mgr_dicts)
            stmt = stmt.on_conflict_do_update(
                index_elements=["cik"], set_={"name": stmt.excluded.name}
            )
            session.execute(stmt)
            stats["managers"] = len(mgr_dicts)

        if filing_dicts:
            session.bulk_insert_mappings(Filing, filing_dicts)
            stats["filings"] = len(filing_dicts)

        session.commit()
        valid_accessions = {f["accession_number"] for f in filing_dicts}
        del submissions, coverpages, summaries, filing_dicts

        _ingest_status["detail"] = "Downloading INFOTABLE.tsv (~343MB)..."
        infotable_path = download_tsv_to_file("INFOTABLE.tsv")

        BATCH_SIZE = 10_000
        holdings_batch = []
        issuers_seen = set()
        issuers_batch = []
        total_holdings = 0
        skipped = 0

        with open(infotable_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                acc_num = row["ACCESSION_NUMBER"]
                if acc_num not in valid_accessions:
                    skipped += 1
                    continue

                cusip = row["CUSIP"]
                if cusip not in issuers_seen:
                    issuers_seen.add(cusip)
                    issuers_batch.append({
                        "cusip": cusip,
                        "name": row["NAMEOFISSUER"],
                        "figi": row["FIGI"] if row.get("FIGI") else None,
                    })
                    if len(issuers_batch) >= 5000:
                        stmt = pg_insert(Issuer).values(issuers_batch)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["cusip"],
                            set_={"name": stmt.excluded.name, "figi": stmt.excluded.figi},
                        )
                        session.execute(stmt)
                        session.commit()
                        issuers_batch = []

                try:
                    holdings_batch.append({
                        "accession_number": acc_num,
                        "cusip": cusip,
                        "title_of_class": row["TITLEOFCLASS"],
                        "value": int(row["VALUE"] or 0),
                        "shares_or_principal": int(row["SSHPRNAMT"] or 0),
                        "sh_or_prn": row["SSHPRNAMTTYPE"],
                        "investment_discretion": row["INVESTMENTDISCRETION"],
                        "put_call": row["PUTCALL"] if row.get("PUTCALL") else None,
                        "voting_authority_sole": int(row["VOTING_AUTH_SOLE"] or 0),
                        "voting_authority_shared": int(row["VOTING_AUTH_SHARED"] or 0),
                        "voting_authority_none": int(row["VOTING_AUTH_NONE"] or 0),
                    })
                except (ValueError, KeyError):
                    continue

                if len(holdings_batch) >= BATCH_SIZE:
                    if issuers_batch:
                        stmt = pg_insert(Issuer).values(issuers_batch)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["cusip"],
                            set_={"name": stmt.excluded.name, "figi": stmt.excluded.figi},
                        )
                        session.execute(stmt)
                        issuers_batch = []
                    session.bulk_insert_mappings(Holding, holdings_batch)
                    session.commit()
                    total_holdings += len(holdings_batch)
                    holdings_batch = []
                    if total_holdings % 100_000 == 0:
                        _ingest_status["detail"] = f"{total_holdings:,} holdings loaded..."
                        _ingest_status["stats"] = {**stats, "holdings": total_holdings}
                        logger.info(f"  ... {total_holdings:,} holdings loaded")

        if issuers_batch:
            stmt = pg_insert(Issuer).values(issuers_batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["cusip"],
                set_={"name": stmt.excluded.name, "figi": stmt.excluded.figi},
            )
            session.execute(stmt)
        if holdings_batch:
            session.bulk_insert_mappings(Holding, holdings_batch)
            total_holdings += len(holdings_batch)

        session.commit()
        session.close()

        import os as _os
        _os.unlink(infotable_path)

        stats["issuers"] = len(issuers_seen)
        stats["holdings"] = total_holdings
        _ingest_status = {
            "state": "completed",
            "detail": f"Done! {total_holdings:,} holdings loaded",
            "stats": stats,
            "skipped_holdings": skipped,
        }
        logger.info(f"Ingestion complete: {stats}")

    except Exception as e:
        logger.error(f"Ingestion error: {e}", exc_info=True)
        _ingest_status = {"state": "error", "detail": str(e), "stats": stats}
        try:
            session.rollback()
            session.close()
        except Exception:
            pass


@app.post("/api/v1/ingest", tags=["Admin"])
async def start_ingestion():
    """Start background ingestion."""
    import threading
    if _ingest_status["state"] == "running":
        return {"status": "already_running", "detail": _ingest_status["detail"]}
    thread = threading.Thread(target=_run_ingestion_background, daemon=True)
    thread.start()
    return {"status": "started", "message": "Check GET /api/v1/ingest/status"}


@app.get("/api/v1/ingest/status", tags=["Admin"])
async def ingestion_status():
    """Check ingestion status."""
    return _ingest_status


# Analytics and cache endpoints
from .analytics import analytics
from .cache import query_cache


@app.get("/api/v1/analytics", tags=["Analytics"])
async def get_analytics():
    """
    Get query analytics.

    Returns statistics about API usage, query performance, and errors.
    """
    return analytics.get_stats()


@app.get("/api/v1/cache/stats", tags=["Cache"])
async def get_cache_stats():
    """
    Get cache statistics.

    Returns cache hit rate, size, and configuration.
    """
    return query_cache.get_stats()


@app.post("/api/v1/cache/clear", tags=["Cache"])
async def clear_cache():
    """
    Clear the query cache.

    Removes all cached queries and resets statistics.
    """
    query_cache.clear()
    return {"status": "success", "message": "Cache cleared"}


# Import routers
from .routers import query, managers, filings, holdings, analytics_endpoints, watchlist, auth, rag

# Authentication router
app.include_router(auth.router, prefix="/api/v1", tags=["Authentication"])

# Natural language query router
app.include_router(query.router, prefix="/api/v1", tags=["Query"])

# RAG / Semantic search router
app.include_router(rag.router, prefix="/api/v1", tags=["Semantic Search"])

# REST data access routers
app.include_router(managers.router, prefix="/api/v1", tags=["Managers"])
app.include_router(filings.router, prefix="/api/v1", tags=["Filings"])
app.include_router(holdings.router, prefix="/api/v1", tags=["Holdings"])

# Analytics routers
app.include_router(analytics_endpoints.router, prefix="/api/v1", tags=["Analytics"])

# Watchlist router (requires authentication)
app.include_router(watchlist.router, prefix="/api/v1", tags=["Watchlist"])


if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
