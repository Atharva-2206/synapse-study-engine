import streamlit as st
import os
from src.engine import SynapseEngine
from src.prompts import PERSONAS

st.set_page_config(page_title="Synapse - Deep Research", layout="wide")

engine = SynapseEngine()

st.title("🧠 Synapse: Contextual Study Engine")

with st.sidebar:
    mode = st.selectbox("Choose Learning Mode", list(PERSONAS.keys()))
    uploaded_file = st.file_uploader("Upload Academic Material", type=['pdf', 'png', 'jpg'])

if uploaded_file:
    # Save file locally for File API ingestion
    temp_path = f"data/{uploaded_file.name}"
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.info("Ingesting Multimodal Layout...")
    # This bypasses standard text extraction
    gemini_file = engine.upload_to_gemini(temp_path)
    
    user_query = st.text_input("What concept should we explore in this dossier?")

    if st.button("Generate Study Dossier"):
        with st.spinner("Executing Deep Research..."):
            dossier = engine.generate_dossier(gemini_file, user_query, PERSONAS[mode])
            
            st.markdown("### 📋 The Synapse Study Dossier")
            st.markdown(dossier)
            
            # Clean up
            os.remove(temp_path)