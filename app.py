import streamlit as st
import os
import re
import plotly.express as px
from streamlit_mermaid import st_mermaid
from src.engine import SynapseEngine
from src.utils import process_pdf, text_to_audio
from src.prompts import PERSONAS

# 1. Session State Initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "engine" not in st.session_state:
    st.session_state.engine = SynapseEngine()
if "current_file" not in st.session_state:
    st.session_state.current_file = None

st.set_page_config(page_title="Synapse AI", layout="wide")
st.title("🧠 Synapse: Interactive Study Engine")

# 2. Sidebar - Setup & Persistent Settings
with st.sidebar:
    st.header("Tutor Settings")
    mode = st.selectbox("Persona Mode", list(PERSONAS.keys()))
    uploaded_file = st.file_uploader("Upload PDF", type=['pdf'])
    
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# 3. Persistent File Ingestion
if uploaded_file and (st.session_state.current_file != uploaded_file.name):
    with st.spinner("Ingesting Visual & Textual Context..."):
        raw_text, pdf_img = process_pdf(uploaded_file)
        st.session_state.engine.ingest_local_context(raw_text)
        
        # Save for File API
        temp_path = f"data/{uploaded_file.name}"
        if not os.path.exists("data"): os.makedirs("data")
        with open(temp_path, "wb") as f: f.write(uploaded_file.getbuffer())
        
        st.session_state.gemini_file = st.session_state.engine.upload_to_gemini(temp_path)
        st.session_state.current_file = uploaded_file.name
        st.success(f"Loaded: {uploaded_file.name}")

# 4. Chat Interface
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask Synapse anything..."):
    # Display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate Assistant Response
    with st.chat_message("assistant"):
        with st.spinner("Synapse is thinking..."):
            # ROUTING LOGIC: Only trigger Exa.ai for Deep Study
            use_external = mode in ["Deep Study (STEM/Research)", "Global Scholar (ESL)"]
            
            response_text = st.session_state.engine.generate_dossier(
                st.session_state.gemini_file, 
                prompt, 
                PERSONAS[mode],
                use_external=use_external
            )
            
            # --- RENDER LOGIC ---
            
            # A. Handle Mermaid Diagrams
            mermaid_match = re.search(r"```mermaid\s+(.*?)\s+```", response_text, re.DOTALL)
            if mermaid_match:
                mermaid_code = mermaid_match.group(1)
                st_mermaid(mermaid_code)
                response_text = re.sub(r"```mermaid.*?```", "*(Visual Roadmap Generated Above)*", response_text, flags=re.DOTALL)

            # B. Handle Plotly Graphs
            plotly_match = re.search(r"```python_plotly\s+(.*?)\s+```", response_text, re.DOTALL)
            if plotly_match:
                try:
                    # Creating a safe execution environment for Plotly code
                    exec_globals = {"px": px, "fig": None}
                    exec(plotly_match.group(1), exec_globals)
                    if exec_globals["fig"]:
                        st.plotly_chart(exec_globals["fig"])
                except Exception as e:
                    st.error(f"Graph Error: {e}")
                response_text = re.sub(r"```python_plotly.*?```", "*(Interactive Graph Generated Above)*", response_text, flags=re.DOTALL)

            st.markdown(response_text)
            
            # Save to history
            st.session_state.messages.append({"role": "assistant", "content": response_text})