from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs" / "yc-founders.json"
DB = Path(__file__).resolve().parent / "progress.db"


def load_companies() -> list[dict]:
    with SOURCE.open(encoding="utf-8") as handle:
        records = json.load(handle)
    grouped: dict[str, dict] = {}
    for record in records:
        company = grouped.setdefault(
            record["name"],
            {key: record.get(key) for key in ("name", "batch", "yc_url", "website", "one_liner", "description")}
            | {"founders": []},
        )
        seen = {(f["name"], f.get("linkedin")) for f in company["founders"]}
        for founder in record.get("founders", []):
            key = (founder.get("name", "").strip(), founder.get("linkedin"))
            if key not in seen:
                company["founders"].append({"name": key[0], "linkedin": key[1]})
                seen.add(key)
    return sorted(grouped.values(), key=lambda item: item["name"].lower())


def founder_id(company: str, founder: dict) -> str:
    value = f"{company}|{founder.get('linkedin') or founder.get('name', '')}"
    return hashlib.sha256(value.encode()).hexdigest()


def init_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB)
    connection.execute("CREATE TABLE IF NOT EXISTS emails (founder_id TEXT PRIMARY KEY, email TEXT NOT NULL)")
    connection.commit()
    return connection


def saved_emails(connection: sqlite3.Connection) -> dict[str, str]:
    return dict(connection.execute("SELECT founder_id, email FROM emails"))


def copy_button(url: str, key: str) -> None:
    safe_url = json.dumps(url)
    components.html(
        f"""<button onclick='navigator.clipboard.writeText({safe_url})'
        style='border:1px solid #c8cdd5;border-radius:6px;background:white;padding:5px 10px;cursor:pointer'>Copy link</button>""",
        height=38,
    )


def csv_bytes(companies: list[dict], emails: dict[str, str]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["company", "founder_name", "email", "linkedin", "one_liner", "batch", "yc_url"])
    writer.writeheader()
    for company in companies:
        for founder in company["founders"]:
            writer.writerow(
                {
                    "company": company["name"],
                    "founder_name": founder["name"],
                    "email": emails.get(founder_id(company["name"], founder), ""),
                    "linkedin": founder.get("linkedin") or "",
                    "one_liner": company.get("one_liner") or "",
                    "batch": company.get("batch") or "",
                    "yc_url": company.get("yc_url") or "",
                }
            )
    return output.getvalue().encode("utf-8-sig")


st.set_page_config(page_title="YC Founder Email Review", page_icon="✉", layout="wide")
st.title("YC Founder Email Review")
st.caption("Work through one company at a time. Your progress is saved locally in SQLite.")

companies = load_companies()
connection = init_db()
emails = saved_emails(connection)

with st.sidebar:
    st.header("Find a company")
    search = st.text_input("Search", placeholder="Company or founder")
    status = st.radio("Show", ["All", "Needs email", "Completed"], horizontal=True)
    filtered = []
    for company in companies:
        matches = not search or search.lower() in json.dumps(company).lower()
        filled = all(emails.get(founder_id(company["name"], founder), "").strip() for founder in company["founders"])
        status_match = status == "All" or (status == "Completed" and filled) or (status == "Needs email" and not filled)
        if matches and status_match:
            filtered.append(company)
    st.caption(f"{len(filtered)} of {len(companies)} companies")
    if not filtered:
        st.warning("No companies match this filter.")
        st.stop()
    labels = [f"{company['name']} ({sum(bool(emails.get(founder_id(company['name'], f), '').strip()) for f in company['founders'])}/{len(company['founders'])})" for company in filtered]
    selected = st.selectbox("Company", range(len(filtered)), format_func=lambda index: labels[index])
    st.divider()
    st.download_button("Download founder CSV", csv_bytes(companies, emails), "yc-founders-with-emails.csv", "text/csv", use_container_width=True)

company = filtered[selected]
st.subheader(company["name"])
meta = " · ".join(value for value in (company.get("batch"), company.get("yc_url")) if value)
st.caption(meta)
if company.get("one_liner"):
    st.info(company["one_liner"])
if company.get("description") and company.get("description") != company.get("one_liner"):
    with st.expander("Company details"):
        st.write(company["description"])

st.markdown("#### Founders")
with st.form(f"company-{selected}"):
    pending: dict[str, str] = {}
    for index, founder in enumerate(company["founders"]):
        fid = founder_id(company["name"], founder)
        left, middle, right = st.columns([2.2, 4, 1.1])
        left.markdown(f"**{founder['name']}**")
        linkedin = founder.get("linkedin") or ""
        if linkedin:
            middle.link_button("Open LinkedIn", linkedin, use_container_width=False)
            copy_button(linkedin, f"copy-{fid}")
        else:
            middle.caption("No LinkedIn link found")
        pending[fid] = right.text_input("Email", value=emails.get(fid, ""), key=f"email-{fid}", label_visibility="collapsed", placeholder="founder@company.com")
    submitted = st.form_submit_button("Save company progress", type="primary", use_container_width=True)

if submitted:
    connection.executemany("INSERT INTO emails(founder_id, email) VALUES (?, ?) ON CONFLICT(founder_id) DO UPDATE SET email=excluded.email", [(fid, email.strip()) for fid, email in pending.items()])
    connection.commit()
    st.success("Progress saved.")
    st.rerun()

connection.close()
