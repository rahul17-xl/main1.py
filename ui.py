import streamlit as st
import requests

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Doc Extraction Engine", page_icon="📄", layout="wide")
st.title("📄 Document Extraction Engine")
st.write("Convert raw unstructured invoices or resumes into reliable validation schemas.")

st.sidebar.header("History Logs")
if st.sidebar.button("Refresh History Logs"):
    st.rerun()

try:
    history_response = requests.get(f"{BACKEND_URL}/extractions").json()
    if history_response:
        for item in reversed(history_response):
            st.sidebar.markdown(f"**{item['filename']}** ({item['type']})  \n*{item['timestamp']}*")
            st.sidebar.markdown("---")
except Exception:
    st.sidebar.info("Start your FastAPI server backend to display real-time history logs.")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Upload Document")
    uploaded_file = st.file_uploader("Choose a file (PDF or TXT)", type=["pdf", "txt"])
    doc_type = st.selectbox("Document Classification Type", options=["Invoice", "Resume"])
    
    if st.button("Extract Data fields ✨", type="primary"):
        if not uploaded_file:
            st.warning("Please upload a file first!")
        else:
            with st.spinner("Extracting structured fields..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                data = {"document_type": doc_type}
                try:
                    response = requests.post(f"{BACKEND_URL}/extract", files=files, data=data)
                    if response.status_code == 200:
                        st.session_state["last_result"] = response.json()
                        st.success("Extraction complete!")
                    else:
                        st.error(f"Error: {response.json().get('detail')}")
                except Exception as e:
                    st.error(f"Cannot connect to backend server. Make sure main.py is running! ({e})")

with col2:
    st.subheader("Extracted Output Schema")
    if "last_result" in st.session_state:
        res = st.session_state["last_result"]
        data_fields = res["result"]
        
        st.info(f"**File:** {res['filename']} | **Type:** {res['type']}")
        
        def render_field(label, field_dict):
            if not field_dict: return
            val = field_dict.get("value")
            conf = field_dict.get("confidence", "low")
            color = "green" if conf == "high" else "orange" if conf == "medium" else "red"
            st.markdown(f"**{label}:** {val if val else '*[Missing]*'}")
            st.markdown(f"**Confidence:** :{color}[{conf.upper()}]")
            st.markdown("---")

        if res["type"].lower() == "invoice":
            render_field("Vendor Name", data_fields.get("vendor"))
            render_field("Billing Date", data_fields.get("date"))
            render_field("Total Value Amount", data_fields.get("total_amount"))
            st.write("**Line Items:**", data_fields.get("line_items", []))
        else:
            render_field("Candidate Name", data_fields.get("candidate_name"))
            st.write("**Identified Skills:**", ", ".join(data_fields.get("skills", [])))
            st.write("**Experience Summary:**", data_fields.get("experience"))
            st.write("**Education Qualifications:**", data_fields.get("education"))
    else:
        st.write("Upload a document file to parse outputs.")
