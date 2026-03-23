import streamlit as st
import os
import re
import plotly.express as px
from streamlit_mermaid import st_mermaid
from src.engine import SynapseEngine
from src.utils import process_file, text_to_audio
from src.prompts import PERSONAS

if "messages" not in st.session_state:
    st.session_state.messages = []
    
if "engine" not in st.session_state or not hasattr(st.session_state.engine, 'clear_context'):
    st.session_state.engine = SynapseEngine()
    
if "uploaded_file_names" not in st.session_state:
    st.session_state.uploaded_file_names = set()
if "gemini_files" not in st.session_state:
    st.session_state.gemini_files = []
    
if "processed_audio_hashes" not in st.session_state:
    st.session_state.processed_audio_hashes = set()

st.set_page_config(page_title="Synapse AI", layout="wide")
st.title("🧠 Synapse: Interactive Study Engine")

with st.sidebar:
    st.header("Tutor Settings")
    mode = st.selectbox("Persona Mode", list(PERSONAS.keys()))
    
    supported_types = ['pdf', 'png', 'jpg', 'jpeg', 'heic', 'docx', 'pptx', 'xlsx', 'csv', 'txt', 'md']
    uploaded_files = st.file_uploader(
        "Upload Study Materials", 
        type=supported_types,
        accept_multiple_files=True
    )
    
    current_file_names = set(f.name for f in uploaded_files) if uploaded_files else set()
    removed_files = st.session_state.uploaded_file_names - current_file_names
    
    if removed_files:
        st.session_state.engine.clear_context()
        st.session_state.uploaded_file_names = set()
        st.session_state.gemini_files = []
    
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()
        
    if st.button("Clear Uploaded Files"):
        st.session_state.uploaded_file_names = set()
        st.session_state.gemini_files = []
        st.session_state.engine.clear_context() 
        st.success("Files cleared from session.")
        st.rerun()

if uploaded_files:
    for uploaded_file in uploaded_files:
        if uploaded_file.name not in st.session_state.uploaded_file_names:
            with st.spinner(f"Ingesting {uploaded_file.name}..."):
                if not os.path.exists("data"): os.makedirs("data")
                temp_path = f"data/{uploaded_file.name}"
                
                with open(temp_path, "wb") as f: 
                    f.write(uploaded_file.getbuffer())
                    
                raw_text = process_file(temp_path)
                if raw_text:
                    st.session_state.engine.ingest_local_context(raw_text)
                
                ext = os.path.splitext(uploaded_file.name)[1].lower()
                upload_path = temp_path
                
                if ext not in ['.pdf', '.png', '.jpg', '.jpeg', '.heic', '.txt', '.csv', '.md']:
                    md_path = f"data/{uploaded_file.name}.txt"
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(raw_text)
                    upload_path = md_path
                    
                gemini_f = st.session_state.engine.upload_to_gemini(upload_path)
                st.session_state.gemini_files.append(gemini_f)
                
                st.session_state.uploaded_file_names.add(uploaded_file.name)
                st.success(f"Loaded: {uploaded_file.name}")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "audio" in message:
            st.audio(message["audio"], format="audio/mp3")

prompt = st.chat_input("Ask Synapse anything...")

audio_prompt = None
if mode == "Commuter Podcast (Audio)":
    audio_prompt = st.audio_input("🎙️ Record a Voice Prompt")

is_new_audio = False
if audio_prompt:
    audio_hash = hash(audio_prompt.getvalue())
    if audio_hash not in st.session_state.processed_audio_hashes:
        is_new_audio = True
        st.session_state.processed_audio_hashes.add(audio_hash)

if prompt or is_new_audio:
    user_text = prompt
    used_audio = False
    
    if is_new_audio and not prompt:
        used_audio = True
        with st.spinner("Transcribing voice prompt..."):
            temp_audio_path = "data/user_voice_prompt.wav"
            if not os.path.exists("data"): os.makedirs("data")
            with open(temp_audio_path, "wb") as f:
                f.write(audio_prompt.getbuffer())
            
            gemini_audio = st.session_state.engine.upload_to_gemini(temp_audio_path)
            transcription = st.session_state.engine.client.models.generate_content(
                model=st.session_state.engine.model_id,
                contents=[gemini_audio, "Transcribe this audio precisely. Output ONLY the transcribed text without quotes, markdown, or extra commentary."]
            ).text.strip()
            user_text = transcription

    display_text = f"🎙️ *{user_text}*" if used_audio else user_text
    st.session_state.messages.append({"role": "user", "content": display_text})
    with st.chat_message("user"):
        st.markdown(display_text)

    with st.chat_message("assistant"):
        with st.spinner("Synapse is thinking..."):
            use_external = mode in ["Deep Study (STEM/Research)", "Global Scholar (ESL)", "Critical Analyst (Humanities/Bio)"]
            
            response_text = st.session_state.engine.generate_dossier(
                st.session_state.gemini_files, 
                user_text, 
                PERSONAS[mode],
                use_external=use_external
            )
            
            audio_bytes = None
            
            # --- RENDER LOGIC ---
            if mode == "Commuter Podcast (Audio)":
                # Render Audio Player with Autoplay activated!
                st.markdown(response_text)
                audio_fp = text_to_audio(response_text)
                audio_bytes = audio_fp.read()
                st.audio(audio_bytes, format="audio/mp3", autoplay=True)
            else:
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
                        exec_globals = {"px": px, "fig": None}
                        exec(plotly_match.group(1), exec_globals)
                        if exec_globals["fig"]:
                            st.plotly_chart(exec_globals["fig"])
                    except Exception as e:
                        st.error(f"Graph Error: {e}")
                    response_text = re.sub(r"```python_plotly.*?```", "*(Interactive Graph Generated Above)*", response_text, flags=re.DOTALL)

                st.markdown(response_text)
            
            message_data = {"role": "assistant", "content": response_text}
            if audio_bytes:
                message_data["audio"] = audio_bytes
            st.session_state.messages.append(message_data)