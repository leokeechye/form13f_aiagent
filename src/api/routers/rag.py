"""
RAG Router

Semantic search endpoints for filing text content.
"""

from fastapi import APIRouter, HTTPException, status
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import logging
import os

from ..schemas import (
    SemanticSearchRequest,
    SemanticSearchResponse,
    FilingTextResponse
)
from ...tools.rag_tool import RAGRetrievalTool
from litellm import completion

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize RAG tool (shared across requests)
try:
    rag_tool = RAGRetrievalTool()
    logger.info("RAG tool initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize RAG tool: {e}")
    rag_tool = None


@router.post("/search/semantic", response_model=SemanticSearchResponse)
async def semantic_search(request: SemanticSearchRequest):
    """
    Search Form 13F filing text using semantic search.

    This endpoint uses AI-powered semantic search to find relevant sections
    in Form 13F filings based on meaning, not just keywords.

    **IMPORTANT LIMITATIONS:**
    Form 13F filings are regulatory documents that report holdings (what stocks/positions
    managers own). They typically do NOT contain:
    - Detailed investment strategies or philosophies
    - Investment theses or rationales for holdings
    - Market commentary or analysis
    - Future investment plans or outlooks

    **What IS in Form 13F filings:**
    - Manager contact information and details
    - Amendment notices and explanations
    - Regulatory disclosures and boilerplate
    - Notes about fund structure and relying advisers
    - Occasional brief explanatory notes about filing changes

    **Best use cases for semantic search:**
    - "filing manager" (returns manager contact details)
    - "relying adviser" (finds third-party management disclosures)
    - "confidential treatment" (finds filings with omitted info)
    - "education fund" (specific fund type searches)
    - "Israel" or "California" (location-based searches)

    **NOT recommended (limited/no data):**
    - "What investment strategies do managers use?" ❌
    - "Find filings discussing AI or technology investments" ❌
    - "What is [manager]'s investment philosophy?" ❌

    For analyzing actual investment positions and holdings data,
    use the SQL query endpoints instead.

    **Parameters:**
    - `query`: Your search query (3-500 characters)
    - `top_k`: Number of results to return (1-20, default: 5)
    - `filter_accession`: Optional - filter to specific filing
    - `filter_content_type`: Optional - filter to specific content type
      (e.g., "explanatory_notes", "cover_page_info", "amendment_info")

    **Returns:**
    - List of matching text sections with relevance scores
    - Each result includes:
      - Text content
      - Accession number (filing ID)
      - Content type (section of filing)
      - Relevance score (0.0-1.0)
    """
    logger.info(f"Semantic search: {request.query[:100]}...")

    if not rag_tool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Semantic search is currently unavailable. Qdrant vector database may not be running."
        )

    try:
        # Execute semantic search
        result = rag_tool.execute(
            query=request.query,
            top_k=request.top_k,
            filter_accession=request.filter_accession,
            filter_content_type=request.filter_content_type,
            filter_cik_company=request.filter_cik_company,
            filter_section=request.filter_section,
            filter_year=request.filter_year
        )

        if not result.get("success"):
            error_msg = result.get("error", "Unknown error during search")
            logger.error(f"Search failed: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_msg
            )

        logger.info(f"Search completed: {result.get('results_count', 0)} results")

        return SemanticSearchResponse(
            success=True,
            results=result.get("results", []),
            results_count=result.get("results_count", 0),
            query=request.query
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Semantic search error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/filings/{accession_number}/text", response_model=FilingTextResponse)
async def get_filing_text(
    accession_number: str,
    content_type: Optional[str] = None
):
    """
    Get text content for a specific Form 13F filing.

    Returns all text sections extracted from a filing, or filter to a specific
    content type (e.g., explanatory notes, cover page).

    **Parameters:**
    - `accession_number`: SEC accession number (e.g., "0001067983-25-000001")
    - `content_type`: Optional - filter to specific section type

    **Returns:**
    - Filing metadata (accession number)
    - Text sections organized by content type
    - List of available content types
    """
    logger.info(f"Get filing text: {accession_number}")

    if not rag_tool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Filing text service is currently unavailable."
        )

    try:
        # Get filing text summary
        result = rag_tool.get_filing_text_summary(accession_number)

        if not result.get("success"):
            error_msg = result.get("error", "Filing not found")
            logger.warning(f"Filing text not found: {accession_number}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )

        sections = result.get("sections", {})
        sections_found = result.get("sections_found", [])

        # Filter to specific content type if requested
        if content_type:
            if content_type not in sections:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Content type '{content_type}' not found in this filing"
                )
            sections = {content_type: sections[content_type]}
            sections_found = [content_type]

        logger.info(f"Filing text retrieved: {len(sections_found)} sections")

        return FilingTextResponse(
            success=True,
            accession_number=accession_number,
            sections=sections,
            sections_found=sections_found,
            total_sections=len(sections_found)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get filing text error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve filing text: {str(e)}"
        )


class SummarizeRequest(BaseModel):
    """Request to summarize search results with AI"""
    query: str = Field(..., description="Original search query")
    results: List[Dict[str, Any]] = Field(..., description="Search results to summarize")


class SummarizeResponse(BaseModel):
    """AI-generated summary of search results"""
    success: bool
    summary: str
    query: str


@router.post("/search/summarize", response_model=SummarizeResponse)
async def summarize_results(request: SummarizeRequest):
    """
    Summarize semantic search results using Claude AI.

    This endpoint takes search results and generates a financial analyst-style
    summary using Claude. It costs money per request (~$0.005-0.01).

    **Parameters:**
    - `query`: The original search query
    - `results`: List of search results to summarize

    **Returns:**
    - AI-generated summary analyzing the search results
    """
    logger.info(f"Summarizing results for query: {request.query[:100]}...")

    if not request.results:
        return SummarizeResponse(
            success=True,
            summary="No results to summarize.",
            query=request.query
        )

    try:
        # Build context from results
        context = ""
        for i, result in enumerate(request.results, 1):
            context += f"\n\n=== Result {i} ===\n"
            context += f"Section: {result.get('content_type', 'Unknown')}\n"
            context += f"Relevance: {result.get('relevance_score', 0):.2%}\n"
            context += f"Text: {result.get('text', '')}\n"

        # Get LLM configuration
        llm_provider = os.getenv("LLM_PROVIDER", "anthropic")
        llm_model = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
        model_name = f"{llm_provider}/{llm_model}"

        # Create prompt
        prompt = f"""You are a financial analyst reviewing SEC Form 10-K filing excerpts.

User Query: "{request.query}"

Below are the most relevant excerpts from company 10-K filings:

{context}

Please provide a clear, professional analysis that:
1. Directly answers the user's question
2. Synthesizes information across all excerpts
3. Highlights key risks, opportunities, or insights
4. Uses specific details from the text
5. Keeps it concise (2-3 paragraphs)

Respond as a financial analyst would - professional, analytical, and focused on investment-relevant insights."""

        # Call Claude
        response = completion(
            model=model_name,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=800,
            temperature=0.3
        )

        summary = response.choices[0].message.content

        logger.info(f"Summary generated successfully ({len(summary)} chars)")

        return SummarizeResponse(
            success=True,
            summary=summary,
            query=request.query
        )

    except Exception as e:
        logger.error(f"Summarize error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate summary: {str(e)}"
        )
