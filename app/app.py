from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from supabase import Client, create_client

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs" / "yc-founders.json"


def get_client() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def load_companies() -> list[dict]:
    with SOURCE.open(encoding="utf-8") as handle:
        records = json.load(handle)
    grouped = {}
    for record in records:
        company = grouped.setdefault(record["name"], {key: record.get(key) for key in ("name", "batch", "yc_url", "website", "one_liner", "description")} | {"founders": []})
        seen = {(f["name"], f.get("linkedin")) for f in company["founders"]}
        for founder in record.get("founders", []):
            item = {"name": founder.get("name", "").strip(), "linkedin": founder.get("linkedin") or ""}
            if (item["name"], item["linkedin"]) not in seen:
                company["founders"].append(item)
                seen.add((item["name"], item["linkedin"]))
    return sorted(grouped.values(), key=lambda item: item["name"].lower())


def founder_id(company: str, founder: dict) -> str:
    return hashlib.sha256(f"{company}|{founder.get('linkedin') or founder['name']}".encode()).hexdigest()


def copy_button(url: str, key: str) -> None:
    value = json.dumps(url)
    components.html(f"""
    <button id="{key}" style="border:1px solid #c8cdd5;border-radius:6px;background:white;padding:5px 10px;cursor:pointer">Copy link</button>
    <script>
    const button = document.getElementById("{key}");
    button.addEventListener("click", async () => {{
        let copied = false;
        try {{
            await navigator.clipboard.writeText({value});
            copied = true;
        }} catch (error) {{}}
        if (!copied) {{
            const area = document.createElement("textarea");
            area.value = {value};
            area.style.position = "fixed";
            area.style.opacity = "0";
            document.body.appendChild(area);
            area.focus();
            area.select();
            copied = document.execCommand("copy");
            area.remove();
        }}
        button.textContent = copied ? "Link copied" : "Copy failed";
        setTimeout(() => button.textContent = "Copy link", 1800);
    }});
    </script>
    """, height=42)


def export_csv(companies: list[dict], emails: dict[str, str]) -> bytes:
    output = io.StringIO()
    fields = ["company", "founder_name", "email", "linkedin", "one_liner", "batch", "yc_url"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for company in companies:
        for founder in company["founders"]:
            email = emails.get(founder_id(company["name"], founder), "").strip()
            if not email:
                continue
            writer.writerow({"company": company["name"], "founder_name": founder["name"], "email": email, "linkedin": founder["linkedin"], "one_liner": company.get("one_liner", ""), "batch": company.get("batch", ""), "yc_url": company.get("yc_url", "")})
    return output.getvalue().encode("utf-8-sig")


def login(client: Client) -> None:
    st.title("YC Founder Email Review")
    st.caption("Sign in to save your progress across devices.")
    mode = st.radio("Account", ["Sign in", "Create account"], horizontal=True)
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    if st.button(mode, type="primary"):
        try:
            result = client.auth.sign_in_with_password({"email": email, "password": password}) if mode == "Sign in" else client.auth.sign_up({"email": email, "password": password})
            if result.user and result.session:
                st.session_state.user = result.user
                st.session_state.session = result.session
                st.rerun()
            elif result.user:
                st.success("Account created. Confirm your email, then sign in.")
        except Exception as error:
            st.error(str(error))


st.set_page_config(page_title="YC Founder Email Review", page_icon="✉", layout="wide")
client = get_client()
if "user" not in st.session_state:
    login(client)
    st.stop()

session = st.session_state.get("session")
if session:
    client.auth.set_session(session.access_token, session.refresh_token)

user_id = st.session_state.user.id
progress = client.table("founder_progress").select("founder_id,email").eq("user_id", user_id).execute().data
emails = {row["founder_id"]: row["email"] for row in progress}
custom = client.table("custom_companies").select("data").eq("user_id", user_id).execute().data
companies = load_companies() + [row["data"] for row in custom]
state = client.table("user_state").select("current_company_id").eq("user_id", user_id).execute().data
last_company = state[0]["current_company_id"] if state else None

with st.sidebar:
    st.caption(st.session_state.user.email)
    if st.button("Sign out"):
        client.auth.sign_out()
        st.session_state.clear()
        st.rerun()
    search = st.text_input("Search company or founder")
    status = st.radio("Show", ["All", "Needs email", "Completed"], horizontal=True)
    filtered = []
    for company in companies:
        complete = all(emails.get(founder_id(company["name"], founder), "").strip() for founder in company["founders"])
        matches = not search or search.lower() in json.dumps(company).lower()
        visible = status == "All" or (status == "Completed" and complete) or (status == "Needs email" and not complete)
        if matches and visible:
            filtered.append(company)
    if not filtered:
        st.warning("No companies match this filter.")
        st.stop()
    labels = [f"{c['name']} ({sum(bool(emails.get(founder_id(c['name'], f), '').strip()) for f in c['founders'])}/{len(c['founders'])})" for c in filtered]
    default = next((i for i, c in enumerate(filtered) if c["name"] == last_company), 0)
    selected = st.selectbox("Company", range(len(filtered)), index=default, format_func=lambda i: labels[i])
    st.download_button("Download my CSV", export_csv(companies, emails), "yc-founders-with-emails.csv", "text/csv", use_container_width=True)
    with st.expander("Add a company"):
        with st.form("add-company"):
            name = st.text_input("Company name")
            one_liner = st.text_input("One-liner")
            batch = st.text_input("Batch")
            yc_url = st.text_input("YC URL")
            founder_lines = st.text_area("Founders", placeholder="Name | LinkedIn URL")
            add = st.form_submit_button("Add company")
        if add:
            founders = []
            for line in founder_lines.splitlines():
                founder_name, separator, linkedin = line.partition("|")
                if founder_name.strip():
                    founders.append({"name": founder_name.strip(), "linkedin": linkedin.strip() if separator else ""})
            if not name.strip() or not founders:
                st.error("Company name and one founder are required.")
            else:
                data = {"name": name.strip(), "one_liner": one_liner.strip(), "batch": batch.strip(), "yc_url": yc_url.strip(), "website": "", "description": "", "founders": founders}
                company_id = hashlib.sha256(f"{user_id}|{name.strip()}".encode()).hexdigest()
                client.table("custom_companies").upsert({"user_id": user_id, "company_id": company_id, "data": data}).execute()
                st.rerun()

company = filtered[selected]
try:
    client.table("user_state").upsert({"user_id": user_id, "current_company_id": company["name"]}).execute()
except Exception:
    # Resume state is optional; email progress must remain usable if this table's policy is unavailable.
    pass
st.subheader(company["name"])
st.caption(" · ".join(value for value in (company.get("batch"), company.get("yc_url")) if value))
if company.get("one_liner"):
    st.info(company["one_liner"])
if company.get("description"):
    with st.expander("Company details"):
        st.write(company["description"])

with st.form(f"company-{selected}"):
    pending = {}
    for founder in company["founders"]:
        fid = founder_id(company["name"], founder)
        left, middle, right = st.columns([2.2, 4, 1.1])
        left.markdown(f"**{founder['name']}**")
        if founder["linkedin"]:
            middle.link_button("Open LinkedIn", founder["linkedin"])
            copy_button(founder["linkedin"], f"copy-{fid}")
        else:
            middle.caption("No LinkedIn link found")
        pending[fid] = right.text_input("Email", value=emails.get(fid, ""), key=f"email-{fid}", label_visibility="collapsed", placeholder="founder@company.com")
    submitted = st.form_submit_button("Save company progress", type="primary", use_container_width=True)
if submitted:
    for fid, email in pending.items():
        client.table("founder_progress").upsert({"user_id": user_id, "founder_id": fid, "email": email.strip()}).execute()
    st.success("Progress saved.")
    st.rerun()
