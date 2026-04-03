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


# Temporary diagnostic endpoint for Supabase Auth connectivity
@app.get("/debug/auth-connectivity", tags=["Debug"])
async def debug_auth_connectivity():
    """Diagnose Supabase Auth connectivity from Railway. TEMPORARY - remove after debugging."""
    import os
    import httpx
    import socket

    supabase_url = os.getenv("SUPABASE_URL", "")
    supabase_key = os.getenv("SUPABASE_ANON_KEY", "")
    results = {"supabase_url": supabase_url}

    # 1. DNS resolution
    try:
        hostname = supabase_url.replace("https://", "").replace("http://", "").rstrip("/")
        addrs = socket.getaddrinfo(hostname, 443)
        results["dns"] = {
            "status": "ok",
            "addresses": list(set(f"{a[4][0]} ({a[0].name})" for a in addrs)),
        }
    except Exception as e:
        results["dns"] = {"status": "error", "error": str(e)}

    # 2. HTTPS connectivity to auth health endpoint
    try:
        r = httpx.get(
            f"{supabase_url}/auth/v1/health",
            headers={"apikey": supabase_key},
            timeout=httpx.Timeout(15.0, connect=10.0),
        )
        results["auth_health"] = {"status": r.status_code, "body": r.text[:200]}
    except Exception as e:
        results["auth_health"] = {"status": "error", "error": f"{type(e).__name__}: {e}"}

    # 3. Test with IPv4 only
    try:
        transport = httpx.HTTPTransport(local_address="0.0.0.0")
        with httpx.Client(transport=transport, timeout=httpx.Timeout(15.0, connect=10.0)) as client:
            r = client.get(
                f"{supabase_url}/auth/v1/health",
                headers={"apikey": supabase_key},
            )
            results["auth_health_ipv4"] = {"status": r.status_code, "body": r.text[:200]}
    except Exception as e:
        results["auth_health_ipv4"] = {"status": "error", "error": f"{type(e).__name__}: {e}"}

    return results


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
