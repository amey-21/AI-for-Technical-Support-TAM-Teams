"""Non-technical Streamlit workspace for TAMs and support agents.

Run with: streamlit run ui/app.py
"""
from pathlib import Path
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.account_brief import get_account_brief
from src.common.data import accounts
from src.common.models import TicketInput
from src.triage import triage_ticket

st.set_page_config(page_title="Support & TAM Workspace", page_icon="✨", layout="wide")
st.title("Support & TAM Workspace")
st.caption("A local, deterministic assistant for ticket triage and account preparation.")

triage_tab, account_tab = st.tabs(["Ticket triage", "Account health brief"])

with triage_tab:
    st.subheader("Triage an incoming support ticket")
    st.caption("Paste the customer’s message. The result is a first-response draft for agent review.")
    subject = st.text_input("Subject", placeholder="e.g. Production pipeline timeout")
    body = st.text_area("Ticket details", height=210, placeholder="Paste the ticket text here…")
    if st.button("Triage ticket", type="primary", use_container_width=True):
        if not body.strip():
            st.warning("Enter ticket details before running triage.")
        else:
            with st.spinner("Classifying ticket and checking the knowledge base…"):
                result = triage_ticket(TicketInput(subject=subject, body=body))
            first, second, third = st.columns(3)
            first.metric("Product area", result.product_area)
            second.metric("Category", result.category)
            third.metric("Urgency", result.urgency)
            st.markdown("#### Routing recommendation")
            st.success(result.recommended_team)
            st.markdown("#### Why this was selected")
            st.write(result.reasoning)
            if result.matched_kb_doc:
                st.markdown("#### Matching knowledge-base reference")
                st.code(result.matched_kb_doc, language=None)
            st.markdown("#### Draft response")
            st.info(result.draft_response)

with account_tab:
    st.subheader("Prepare an account health brief")
    account_options = {f"{account['company']} — {account['account_id']}": account["account_id"] for account in accounts()}
    selected = st.selectbox("Choose an account", options=list(account_options), index=0)
    account_id = account_options[selected]
    if st.button("Generate TAM brief", type="primary", use_container_width=True):
        with st.spinner("Reviewing account context and the dataset-relative 90-day ticket window…"):
            brief = get_account_brief(account_id)
        if brief is None:
            st.error("The selected account could not be found.")
        else:
            left, middle, right = st.columns(3)
            left.metric("Account", brief.company)
            middle.metric("Recent tickets", brief.tickets_considered)
            right.metric("Window", f"{brief.ticket_window_start} to {brief.ticket_window_end}")
            st.markdown("#### Executive summary")
            st.write(brief.executive_summary)
            st.markdown("#### Open risks & flagged issues")
            if not brief.open_risks_and_flagged_issues:
                st.success("No ticket or account escalation risks were flagged in this window.")
            for risk in brief.open_risks_and_flagged_issues:
                with st.expander(f"{risk.severity.upper()} — {risk.risk}"):
                    st.caption(f"Source: {risk.source}")
                    if risk.evidence_quote:
                        st.markdown(f"> {risk.evidence_quote}")
            st.markdown("#### Recommended talking points")
            for point in brief.recommended_talking_points:
                st.markdown(f"- {point}")
