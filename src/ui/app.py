"""
Streamlit UI for Form 13F AI Agent

A chat interface for querying institutional holdings data with visualizations.
"""

import streamlit as st
import httpx
import os
from typing import Optional, List, Dict, Any
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Import auth UI components
try:
    from auth_ui import require_auth, show_logout_button, get_auth_headers
    from watchlist_ui import show_watchlist_sidebar
    from rag_ui import render_semantic_search_tab, render_filing_text_explorer_tab
except ImportError:
    # Try alternate import path for different deployment environments
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from auth_ui import require_auth, show_logout_button, get_auth_headers
    from watchlist_ui import show_watchlist_sidebar
    from rag_ui import render_semantic_search_tab, render_filing_text_explorer_tab

# Configuration
# Use Railway API in production, local API in development
# Default to Railway API - only use localhost if explicitly set
API_BASE_URL = os.getenv("API_BASE_URL", "https://form13faiagent-production.up.railway.app")
TIMEOUT = 120.0  # 2 minutes timeout for agent queries

# Override to localhost ONLY if ENVIRONMENT=development is explicitly set
if os.getenv("ENVIRONMENT") == "development":
    API_BASE_URL = "http://localhost:8000"
    print(f"🔧 Development mode: Using local API at {API_BASE_URL}")

# Debug: Log the API URL being used
print(f"🌐 API Base URL: {API_BASE_URL}")
print(f"📍 Environment: {os.getenv('ENVIRONMENT', 'not set')}")

# Page configuration
st.set_page_config(
    page_title="Form 13F AI Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Require authentication
if not require_auth(API_BASE_URL):
    st.stop()  # Stop execution if not authenticated

# Show logout button
show_logout_button()

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f2937;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #6b7280;
        margin-bottom: 2rem;
    }
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
    }
    .stat-value {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
        white-space: nowrap;
    }
    .stat-label {
        font-size: 0.875rem;
        opacity: 0.9;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .sql-box {
        background-color: #1e293b;
        color: #10b981;
        padding: 1rem;
        border-radius: 8px;
        font-family: 'Courier New', monospace;
        font-size: 0.875rem;
        overflow-x: auto;
    }
    .example-query {
        background-color: #f3f4f6;
        padding: 0.75rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
        margin: 0.5rem 0;
        cursor: pointer;
        transition: background-color 0.2s;
    }
    .example-query:hover {
        background-color: #e5e7eb;
    }

    /* Fix chat input to bottom and ensure proper scrolling */
    .stChatFloatingInputContainer {
        position: sticky !important;
        bottom: 0 !important;
        background-color: white !important;
        border-top: 1px solid #e5e7eb !important;
        padding: 1rem !important;
        z-index: 999 !important;
        margin-top: auto !important;
    }

    /* Ensure chat messages container scrolls properly */
    section.main > div {
        display: flex !important;
        flex-direction: column !important;
        height: 100vh !important;
    }

    /* Chat messages should scroll */
    [data-testid="stVerticalBlock"] {
        overflow-y: auto !important;
        flex: 1 !important;
    }
</style>
<script>
    // Auto-scroll to bottom when new messages appear
    window.addEventListener('load', function() {
        const observer = new MutationObserver(function() {
            window.scrollTo(0, document.body.scrollHeight);
        });
        observer.observe(document.body, { childList: true, subtree: true });
    });
</script>
""", unsafe_allow_html=True)


@st.cache_data(ttl=60)
def fetch_stats() -> Optional[dict]:
    """Fetch database statistics"""
    try:
        response = httpx.get(f"{API_BASE_URL}/api/v1/stats", timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch stats: {e}")
        return None


@st.cache_data(ttl=300)
def fetch_managers(name_filter: str = "") -> List[Dict[str, Any]]:
    """Fetch list of managers"""
    try:
        params = {"page_size": 100}
        if name_filter:
            params["name"] = name_filter
        response = httpx.get(f"{API_BASE_URL}/api/v1/managers", params=params, timeout=10.0)
        response.raise_for_status()
        return response.json()["managers"]
    except Exception as e:
        st.error(f"Failed to fetch managers: {e}")
        return []


@st.cache_data(ttl=300)
def fetch_portfolio_composition(cik: str, top_n: int = 20) -> Optional[Dict[str, Any]]:
    """Fetch portfolio composition for a manager"""
    try:
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/analytics/portfolio/{cik}",
            params={"top_n": top_n},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch portfolio: {e}")
        return None


@st.cache_data(ttl=300)
def fetch_security_analysis(cusip: str, top_n: int = 20) -> Optional[Dict[str, Any]]:
    """Fetch security ownership analysis"""
    try:
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/analytics/security/{cusip}",
            params={"top_n": top_n},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch security analysis: {e}")
        return None


@st.cache_data(ttl=300)
def fetch_top_movers(top_n: int = 10) -> Optional[Dict[str, Any]]:
    """Fetch top position movers"""
    try:
        response = httpx.get(
            f"{API_BASE_URL}/api/v1/analytics/movers",
            params={"top_n": top_n},
            timeout=60.0
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Failed to fetch top movers: {e}")
        return None


def query_agent(query: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> dict:
    """Send query to the AI agent with optional conversation history"""
    try:
        payload = {"query": query}

        # Add conversation history if provided
        if conversation_history:
            # Convert to API format (role + content only, exclude other fields)
            payload["conversation_history"] = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in conversation_history
                if msg.get("role") in ["user", "assistant"]
            ]

        # Get auth headers if user is authenticated
        from auth_ui import get_auth_headers
        headers = get_auth_headers() or {}

        response = httpx.post(
            f"{API_BASE_URL}/api/v1/query",
            json=payload,
            headers=headers,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timed out. The query is taking too long to execute."
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to send query: {str(e)}"
        }


def format_number(num: int) -> str:
    """Format large numbers with commas"""
    return f"{num:,}"


def create_portfolio_pie_chart(portfolio_data: Dict[str, Any]) -> go.Figure:
    """Create portfolio composition pie chart"""
    top_holdings = portfolio_data["top_holdings"]

    labels = [h["title_of_class"] for h in top_holdings]
    values = [h["value"] for h in top_holdings]
    percentages = [h["percent_of_portfolio"] for h in top_holdings]

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        textinfo='label+percent',
        hovertemplate='<b>%{label}</b><br>Value: $%{value:,.0f}<br>Portfolio %: %{customdata:.2f}%<extra></extra>',
        customdata=percentages
    )])

    fig.update_layout(
        title=f"Top {len(top_holdings)} Holdings - {portfolio_data['manager_name']}",
        height=500
    )

    return fig


def create_portfolio_bar_chart(portfolio_data: Dict[str, Any]) -> go.Figure:
    """Create portfolio holdings bar chart"""
    top_holdings = portfolio_data["top_holdings"]

    df = pd.DataFrame(top_holdings)
    df = df.sort_values("value", ascending=True)

    fig = go.Figure(data=[go.Bar(
        y=df["title_of_class"],
        x=df["value"],
        orientation='h',
        text=df["percent_of_portfolio"].apply(lambda x: f"{x:.1f}%"),
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Value: $%{x:,.0f}<br>Shares: %{customdata:,.0f}<extra></extra>',
        customdata=df["shares_or_principal"]
    )])

    fig.update_layout(
        title=f"Portfolio Holdings - {portfolio_data['manager_name']}",
        xaxis_title="Value (USD)",
        yaxis_title="",
        height=max(400, len(top_holdings) * 30),
        showlegend=False
    )

    return fig


def create_security_ownership_chart(security_data: Dict[str, Any]) -> go.Figure:
    """Create security ownership bar chart"""
    top_holders = security_data["top_holders"]

    df = pd.DataFrame(top_holders)
    df = df.sort_values("value", ascending=True)

    fig = go.Figure(data=[go.Bar(
        y=df["manager_name"],
        x=df["shares"],
        orientation='h',
        text=df["percent_of_total"].apply(lambda x: f"{x:.1f}%"),
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Shares: %{x:,.0f}<br>Value: $%{customdata:,.0f}<extra></extra>',
        customdata=df["value"]
    )])

    fig.update_layout(
        title=f"Top Institutional Holders - {security_data['title_of_class']}",
        xaxis_title="Shares",
        yaxis_title="",
        height=max(400, len(top_holders) * 30),
        showlegend=False
    )

    return fig


def create_movers_chart(movers_data: Dict[str, Any]) -> go.Figure:
    """Create top movers chart"""
    increases = movers_data.get("biggest_increases", [])[:10]
    decreases = movers_data.get("biggest_decreases", [])[:10]

    # Combine and sort by absolute percentage change
    all_movers = []
    for mover in increases:
        all_movers.append({
            "name": f"{mover['manager_name'][:20]} - {mover['title_of_class'][:20]}",
            "change_pct": mover["value_change_percent"],
            "change_value": mover["value_change"]
        })
    for mover in decreases:
        all_movers.append({
            "name": f"{mover['manager_name'][:20]} - {mover['title_of_class'][:20]}",
            "change_pct": mover["value_change_percent"],
            "change_value": mover["value_change"]
        })

    df = pd.DataFrame(all_movers)
    df = df.sort_values("change_pct", ascending=True)

    # Color based on positive/negative
    colors = ['green' if x > 0 else 'red' for x in df["change_pct"]]

    fig = go.Figure(data=[go.Bar(
        y=df["name"],
        x=df["change_pct"],
        orientation='h',
        marker_color=colors,
        text=df["change_pct"].apply(lambda x: f"{x:+.1f}%"),
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Change: %{x:+.1f}%<br>Value Change: $%{customdata:+,.0f}<extra></extra>',
        customdata=df["change_value"]
    )])

    fig.update_layout(
        title="Biggest Position Changes (Quarter-over-Quarter)",
        xaxis_title="Value Change %",
        yaxis_title="",
        height=max(500, len(all_movers) * 25),
        showlegend=False
    )

    return fig


def render_chat_tab():
    """Render the chat interface tab"""
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Hello! I'm your Form 13F AI assistant. Ask me questions about institutional holdings data."
            }
        ]

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            content = message["content"].replace('∗', '*')
            st.markdown(content, unsafe_allow_html=False)

            # Display SQL if available
            if "sql" in message:
                st.markdown("**Generated SQL:**")
                st.markdown(f'<div class="sql-box">{message["sql"]}</div>', unsafe_allow_html=True)

            # Display table if available
            if "data" in message and message["data"]:
                st.markdown("**Query Results:**")
                df = pd.DataFrame(message["data"])
                st.dataframe(df, use_container_width=True)

                # Download button
                csv = df.to_csv(index=False)
                st.download_button(
                    label="Download CSV",
                    data=csv,
                    file_name="query_results.csv",
                    mime="text/csv"
                )

    # Chat input
    if prompt := st.chat_input("Ask a question about Form 13F holdings..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # Pass conversation history (exclude the welcome message and current prompt)
                history = [
                    msg for msg in st.session_state.messages[:-1]  # Exclude current user message
                    if msg.get("role") in ["user", "assistant"]
                ]
                response = query_agent(prompt, conversation_history=history)

            if response.get("success"):
                answer = response.get("answer", "I found the results for your query.")
                answer = answer.replace('∗', '*')
                st.markdown(answer, unsafe_allow_html=False)

                message_data = {"role": "assistant", "content": answer}

                # Show SQL
                if response.get("sql_query"):
                    st.markdown("**Generated SQL:**")
                    st.markdown(f'<div class="sql-box">{response["sql_query"]}</div>', unsafe_allow_html=True)
                    message_data["sql"] = response["sql_query"]

                # Show data table
                if response.get("raw_data") and len(response["raw_data"]) > 0:
                    st.markdown("**Query Results:**")
                    df = pd.DataFrame(response["raw_data"])
                    st.dataframe(df, use_container_width=True)
                    message_data["data"] = response["raw_data"]

                    # Download button
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name="query_results.csv",
                        mime="text/csv"
                    )

                st.session_state.messages.append(message_data)
            else:
                error_msg = response.get("answer", response.get("error", "Unknown error occurred"))
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"⚠️ {error_msg}"
                })


def render_portfolio_explorer_tab():
    """Render the portfolio explorer tab"""
    st.subheader("Portfolio Explorer")
    st.markdown("Explore institutional investment managers and their portfolio compositions")

    # Manager selection
    col1, col2 = st.columns([3, 1])

    with col1:
        manager_search = st.text_input("Search for a manager", placeholder="e.g., Berkshire Hathaway")

    managers = fetch_managers(manager_search if manager_search else "")

    if managers:
        manager_options = {f"{m['name']} (CIK: {m['cik']})": m['cik'] for m in managers}
        selected_manager = st.selectbox("Select Manager", options=list(manager_options.keys()))

        if selected_manager:
            cik = manager_options[selected_manager]

            with col2:
                top_n = st.slider("Top N Holdings", min_value=5, max_value=50, value=20)

            # Fetch portfolio data
            portfolio_data = fetch_portfolio_composition(cik, top_n)

            if portfolio_data:
                # Add to watchlist button
                auth_headers = get_auth_headers()
                if auth_headers:
                    if st.button(f"⭐ Add {selected_manager.split(' (CIK:')[0]} to Watchlist", key=f"add_mgr_{cik}"):
                        from watchlist_ui import add_to_watchlist
                        if add_to_watchlist(API_BASE_URL, auth_headers, "manager", cik=cik):
                            st.success(f"✅ Added {selected_manager.split(' (CIK:')[0]} to watchlist!")
                            st.rerun()

                # Portfolio summary
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Total Value", f"${portfolio_data['total_value']:,.0f}")
                with col_b:
                    st.metric("Number of Holdings", f"{portfolio_data['number_of_holdings']:,}")
                with col_c:
                    st.metric("Period", portfolio_data['period'])

                # Concentration metrics
                st.markdown("**Concentration Metrics:**")
                col_d, col_e = st.columns(2)
                with col_d:
                    st.info(f"Top 5 Holdings: {portfolio_data['concentration']['top5_percent']}% of portfolio")
                with col_e:
                    st.info(f"Top 10 Holdings: {portfolio_data['concentration']['top10_percent']}% of portfolio")

                st.markdown("---")

                # Visualizations
                viz_tab1, viz_tab2 = st.tabs(["Bar Chart", "Pie Chart"])

                with viz_tab1:
                    fig = create_portfolio_bar_chart(portfolio_data)
                    st.plotly_chart(fig, use_container_width=True)

                with viz_tab2:
                    fig = create_portfolio_pie_chart(portfolio_data)
                    st.plotly_chart(fig, use_container_width=True)

                # Holdings table
                st.markdown("**Holdings Details:**")
                holdings_df = pd.DataFrame(portfolio_data['top_holdings'])
                holdings_df['value'] = holdings_df['value'].apply(lambda x: f"${x:,.0f}")
                holdings_df['shares_or_principal'] = holdings_df['shares_or_principal'].apply(lambda x: f"{x:,.0f}")
                holdings_df['percent_of_portfolio'] = holdings_df['percent_of_portfolio'].apply(lambda x: f"{x:.2f}%")
                st.dataframe(holdings_df, use_container_width=True)
    else:
        st.info("No managers found. Try adjusting your search.")


def render_security_analysis_tab():
    """Render security ownership analysis tab"""
    st.subheader("Security Ownership Analysis")
    st.markdown("Analyze institutional ownership of specific securities")

    # CUSIP input
    cusip_input = st.text_input("Enter CUSIP (9 characters)", placeholder="e.g., 037833100 for Apple")

    if cusip_input and len(cusip_input) == 9:
        top_n = st.slider("Top N Holders", min_value=5, max_value=50, value=20, key="sec_top_n")

        # Fetch security data
        security_data = fetch_security_analysis(cusip_input, top_n)

        if security_data:
            # Security summary
            st.markdown(f"### {security_data['title_of_class']}")

            # Add to watchlist button
            auth_headers = get_auth_headers()
            if auth_headers:
                if st.button(f"⭐ Add {security_data['title_of_class']} to Watchlist", key=f"add_sec_{cusip_input}"):
                    from watchlist_ui import add_to_watchlist
                    if add_to_watchlist(API_BASE_URL, auth_headers, "security", cusip=cusip_input):
                        st.success(f"✅ Added {security_data['title_of_class']} to watchlist!")
                        st.rerun()

            col_a, col_b, col_c, col_d = st.columns(4)
            with col_a:
                st.metric("Total Shares", f"{security_data['total_institutional_shares']:,}")
            with col_b:
                st.metric("Total Value", f"${security_data['total_institutional_value']:,.0f}")
            with col_c:
                st.metric("Number of Holders", f"{security_data['number_of_holders']:,}")
            with col_d:
                st.metric("Period", security_data['period'])

            # Concentration metrics
            st.markdown("**Ownership Concentration:**")
            col_e, col_f, col_g = st.columns(3)
            with col_e:
                st.info(f"Top 5 Holders: {security_data['concentration']['top5_percent']}%")
            with col_f:
                st.info(f"Top 10 Holders: {security_data['concentration']['top10_percent']}%")
            with col_g:
                hhi = security_data['concentration'].get('herfindahl_index', 0)
                st.info(f"Herfindahl Index: {hhi:.4f}")

            st.markdown("---")

            # Visualization
            fig = create_security_ownership_chart(security_data)
            st.plotly_chart(fig, use_container_width=True)

            # Holders table
            st.markdown("**Top Holders Details:**")
            holders_df = pd.DataFrame(security_data['top_holders'])
            holders_df['shares'] = holders_df['shares'].apply(lambda x: f"{x:,.0f}")
            holders_df['value'] = holders_df['value'].apply(lambda x: f"${x:,.0f}")
            holders_df['percent_of_total'] = holders_df['percent_of_total'].apply(lambda x: f"{x:.2f}%")
            st.dataframe(holders_df, use_container_width=True)
    elif cusip_input:
        st.warning("CUSIP must be exactly 9 characters")


def render_top_movers_tab():
    """Render top movers tab"""
    st.subheader("Top Position Changes")
    st.markdown("View the biggest position changes quarter-over-quarter")

    top_n = st.slider("Number of Movers", min_value=5, max_value=50, value=10, key="movers_top_n")

    # Fetch movers data
    movers_data = fetch_top_movers(top_n)

    if movers_data:
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Period From", movers_data['period_from'])
        with col_b:
            st.metric("Period To", movers_data['period_to'])

        st.markdown("---")

        # Visualization
        if movers_data['biggest_increases'] or movers_data['biggest_decreases']:
            fig = create_movers_chart(movers_data)
            st.plotly_chart(fig, use_container_width=True)

        # Detailed tables
        tab1, tab2, tab3, tab4 = st.tabs(["Increases", "Decreases", "New Positions", "Closed Positions"])

        with tab1:
            if movers_data['biggest_increases']:
                st.markdown("**Biggest Increases:**")
                increases_df = pd.DataFrame(movers_data['biggest_increases'])
                increases_df = increases_df[[
                    'manager_name', 'title_of_class', 'previous_value', 'current_value',
                    'value_change', 'value_change_percent'
                ]]
                increases_df['previous_value'] = increases_df['previous_value'].apply(lambda x: f"${x:,.0f}")
                increases_df['current_value'] = increases_df['current_value'].apply(lambda x: f"${x:,.0f}")
                increases_df['value_change'] = increases_df['value_change'].apply(lambda x: f"${x:+,.0f}")
                increases_df['value_change_percent'] = increases_df['value_change_percent'].apply(lambda x: f"{x:+.1f}%")
                st.dataframe(increases_df, use_container_width=True)

        with tab2:
            if movers_data['biggest_decreases']:
                st.markdown("**Biggest Decreases:**")
                decreases_df = pd.DataFrame(movers_data['biggest_decreases'])
                decreases_df = decreases_df[[
                    'manager_name', 'title_of_class', 'previous_value', 'current_value',
                    'value_change', 'value_change_percent'
                ]]
                decreases_df['previous_value'] = decreases_df['previous_value'].apply(lambda x: f"${x:,.0f}")
                decreases_df['current_value'] = decreases_df['current_value'].apply(lambda x: f"${x:,.0f}")
                decreases_df['value_change'] = decreases_df['value_change'].apply(lambda x: f"${x:+,.0f}")
                decreases_df['value_change_percent'] = decreases_df['value_change_percent'].apply(lambda x: f"{x:+.1f}%")
                st.dataframe(decreases_df, use_container_width=True)

        with tab3:
            if movers_data['new_positions']:
                st.markdown("**New Positions:**")
                st.info(f"Total: {len(movers_data['new_positions'])} new positions")
                new_df = pd.DataFrame(movers_data['new_positions'][:20])  # Show top 20
                st.dataframe(new_df, use_container_width=True)

        with tab4:
            if movers_data['closed_positions']:
                st.markdown("**Closed Positions:**")
                st.info(f"Total: {len(movers_data['closed_positions'])} closed positions")
                closed_df = pd.DataFrame(movers_data['closed_positions'][:20])  # Show top 20
                st.dataframe(closed_df, use_container_width=True)


def main():
    # Header
    st.markdown('<div class="main-header">📊 Form 13F AI Agent</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Explore institutional holdings data with AI-powered natural language queries and interactive visualizations</div>', unsafe_allow_html=True)

    # Sidebar with stats
    with st.sidebar:
        st.header("Database Statistics")

        stats = fetch_stats()
        if stats:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-value">{format_number(stats['managers_count'])}</div>
                    <div class="stat-label">Managers</div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-value">{format_number(stats['filings_count'])}</div>
                    <div class="stat-label">Filings</div>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-value">{format_number(stats['issuers_count'])}</div>
                    <div class="stat-label">Issuers</div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                st.markdown(f"""
                <div class="stat-card">
                    <div class="stat-value">{format_number(stats['holdings_count'])}</div>
                    <div class="stat-label">Holdings</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")
            st.info(f"**Latest Quarter:** {stats.get('latest_quarter', 'N/A')}")

            if stats.get('total_value'):
                total_value_billions = stats['total_value'] / 1_000_000_000
                st.success(f"**Total Value:** ${total_value_billions:.2f}B")

        # Show watchlist in sidebar
        auth_headers = get_auth_headers()
        if auth_headers:
            show_watchlist_sidebar(API_BASE_URL, auth_headers)

        st.markdown("---")
        st.markdown("**Quick Navigation:**")
        st.markdown("- 💬 **Chat**: Natural language queries")
        st.markdown("- 📈 **Portfolio Explorer**: Analyze manager portfolios")
        st.markdown("- 🔍 **Security Analysis**: Institutional ownership")
        st.markdown("- 🚀 **Top Movers**: Position changes")
        st.markdown("- 🔎 **Semantic Search**: AI-powered text search")
        st.markdown("- 📄 **Filing Explorer**: View filing text content")

    # Main tabs
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "💬 Chat",
        "🔎 Semantic Search",
        "📈 Portfolio Explorer",
        "🔍 Security Analysis",
        "🚀 Top Movers",
        "📄 Filing Explorer"
    ])

    with tab1:
        render_chat_tab()

    with tab2:
        render_semantic_search_tab(API_BASE_URL)

    with tab3:
        render_portfolio_explorer_tab()

    with tab4:
        render_security_analysis_tab()

    with tab5:
        render_top_movers_tab()

    with tab6:
        render_filing_text_explorer_tab(API_BASE_URL)


if __name__ == "__main__":
    main()
