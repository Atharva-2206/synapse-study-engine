import streamlit as st
import os
import re
import json
import plotly.express as px
from streamlit_mermaid import st_mermaid
from src.engine import SynapseEngine
from src.utils import process_file, text_to_audio
from src.prompts import PERSONAS

st.set_page_config(page_title="Synapse AI", layout="wide")

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stAppDeployButton"] {display: none;}
    
    .synapse-title {
        background: linear-gradient(45deg, #FF4B2B, #FF416C);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        font-size: 3.5rem;
        font-weight: 900;
        margin-bottom: -10px;
    }
    
    .synapse-subtitle {
        text-align: center;
        color: #888;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }

    div[data-testid="stButton"] button {
        border-radius: 12px;
        transition: all 0.3s ease;
        border: 1px solid #e0e0e0;
        font-weight: 600;
    }
    div[data-testid="stButton"] button:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 16px rgba(255, 65, 108, 0.2);
        border-color: #FF416C;
        color: #FF416C;
    }
</style>
""", unsafe_allow_html=True)

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

if "current_persona" not in st.session_state:
    st.session_state.current_persona = "Home"

st.markdown("<h1 class='synapse-title'>🧠 Synapse</h1>", unsafe_allow_html=True)
st.markdown("<p class='synapse-subtitle'>Your AI-powered, multimodal learning companion.</p>", unsafe_allow_html=True)

with st.sidebar:
    st.header("Tutor Settings")
    
    uploaded_files = []
    mode = st.session_state.current_persona
    
    if mode != "Home":
        persona_options = ["🏠 Return to Home"] + list(PERSONAS.keys())
        current_index = persona_options.index(mode)
        
        new_mode = st.selectbox("Persona Mode", persona_options, index=current_index)
        if new_mode != mode:
            if new_mode == "🏠 Return to Home":
                st.session_state.current_persona = "Home"
            else:
                st.session_state.current_persona = new_mode
            st.rerun()
            
        supported_types = ['pdf', 'png', 'jpg', 'jpeg', 'heic', 'csv', 'txt', 'md']
        uploaded_files = st.file_uploader("Upload Study Materials", type=supported_types, accept_multiple_files=True)
        
        if st.button("Clear Chat History"):
            st.session_state.messages = []
            st.rerun()
            
        if st.button("Clear Uploaded Files"):
            st.session_state.uploaded_file_names = set()
            st.session_state.gemini_files = []
            st.session_state.engine.clear_context() 
            st.success("Files cleared from session.")
            st.rerun()
    else:
        st.info("👈 Select a persona from the main dashboard to unlock settings and file uploads.")

if uploaded_files:
    for uploaded_file in uploaded_files:
        if uploaded_file.name not in st.session_state.uploaded_file_names:
            
            def upload_status_callback(msg):
                st.toast(f"⏳ {msg}")
            
            upload_error = None
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
                
                if ext not in ['.pdf', '.png', '.jpg', '.jpeg', '.heic', '.csv', '.txt', '.md']:
                    md_path = f"data/{uploaded_file.name}.txt"
                    with open(md_path, "w", encoding="utf-8") as f:
                        f.write(raw_text)
                    upload_path = md_path
                
                try:
                    gemini_f = st.session_state.engine.upload_to_gemini(upload_path, status_callback=upload_status_callback)
                    st.session_state.gemini_files.append(gemini_f)
                    st.session_state.uploaded_file_names.add(uploaded_file.name)
                except Exception as e:
                    upload_error = str(e)
            
            if upload_error:
                st.error(f"🛑 Upload halted: {upload_error}")
                st.stop()
            else:
                st.success(f"Loaded: {uploaded_file.name}")

if mode == "Home":
    st.markdown("### 🎯 Choose Your Perfect Tutor")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        with st.container(border=True):
            st.subheader("🏃 Sprint Mode")
            st.caption("*Best for: ADHD & Quick Reviews*")
            st.write("Fast-paced, dopamine-driven milestones. Generates visual flowcharts and quick active-recall challenges.")
            if st.button("Select Sprint Mode", use_container_width=True):
                st.session_state.current_persona = "Sprint Mode (Focus)"
                st.rerun()
                
        with st.container(border=True):
            st.subheader("🎧 Commuter Podcast")
            st.caption("*Best for: On-the-Go Learning*")
            st.write("Interact via voice! Converts complex documents into engaging, conversational audio scripts.")
            if st.button("Select Podcast Mode", use_container_width=True):
                st.session_state.current_persona = "Commuter Podcast (Audio)"
                st.rerun()

        with st.container(border=True):
            st.subheader("🌐 Internet Searcher")
            st.caption("*Best for: Instant Web Answers*")
            st.write("Scours the web using Exa.ai to answer any factual question instantly, without needing uploaded files.")
            if st.button("Select Internet Searcher", use_container_width=True):
                st.session_state.current_persona = "Internet Searcher"
                st.rerun()
                
    with col2:
        with st.container(border=True):
            st.subheader("🔬 Deep Study")
            st.caption("*Best for: STEM & Research*")
            st.write("Hardcore technical breakdowns. Extracts LaTeX math, analyzes data trends, and generates Plotly graphs.")
            if st.button("Select Deep Study", use_container_width=True):
                st.session_state.current_persona = "Deep Study (STEM/Research)"
                st.rerun()
                
        with st.container(border=True):
            st.subheader("👁️ Visual Deconstructor")
            st.caption("*Best for: Spatial Reasoning*")
            st.write("Breaks down complex visual charts, diagrams, and data flows step-by-step for visual learners.")
            if st.button("Select Visual Deconstructor", use_container_width=True):
                st.session_state.current_persona = "Visual Deconstructor"
                st.rerun()
                
    with col3:
        with st.container(border=True):
            st.subheader("🌍 Global Scholar")
            st.caption("*Best for: ESL Students*")
            st.write("Bridges language barriers by explaining high-level academic concepts using simple, cross-cultural analogies.")
            if st.button("Select Global Scholar", use_container_width=True):
                st.session_state.current_persona = "Global Scholar (ESL)"
                st.rerun()
                
        with st.container(border=True):
            st.subheader("📖 Critical Analyst")
            st.caption("*Best for: Humanities & Bio*")
            st.write("Acts as a Socratic professor. Focuses on thematic breakdowns, textual evidence, and deep critical thinking.")
            if st.button("Select Critical Analyst", use_container_width=True):
                st.session_state.current_persona = "Critical Analyst (Humanities/Bio)"
                st.rerun()

else:
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
        
        warning_placeholder = st.empty()
        def chat_status_callback(msg):
            warning_placeholder.warning(f"🚦 {msg}")
        
        if is_new_audio and not prompt:
            used_audio = True
            voice_error = None
            
            with st.spinner("Transcribing voice prompt..."):
                temp_audio_path = "data/user_voice_prompt.wav"
                if not os.path.exists("data"): os.makedirs("data")
                with open(temp_audio_path, "wb") as f:
                    f.write(audio_prompt.getbuffer())
                
                try:
                    gemini_audio = st.session_state.engine.upload_to_gemini(temp_audio_path, status_callback=chat_status_callback)
                    transcription_response = st.session_state.engine.rate_limited_generate(
                        contents=[gemini_audio, "Transcribe this audio precisely. Output ONLY the transcribed text without quotes, markdown, or extra commentary."],
                        status_callback=chat_status_callback
                    )
                    user_text = transcription_response.text.strip()
                except Exception as e:
                    voice_error = str(e)
                    
            if voice_error:
                warning_placeholder.empty()
                st.error(f"🛑 Voice processing offline: {voice_error}")
                st.stop()
                
        warning_placeholder.empty()

        display_text = f"🎙️ *{user_text}*" if used_audio else user_text
        st.session_state.messages.append({"role": "user", "content": display_text})
        with st.chat_message("user"):
            st.markdown(display_text)

        with st.chat_message("assistant"):
            gen_warning_placeholder = st.empty()
            def gen_status_callback(msg):
                gen_warning_placeholder.warning(f"🚦 {msg}")

            generation_error = None
            raw_response_text = ""
            
            with st.spinner("Synapse is thinking..."):
                try:
                    use_external = mode in ["Deep Study (STEM/Research)", "Global Scholar (ESL)", "Critical Analyst (Humanities/Bio)", "Internet Searcher"] or not st.session_state.gemini_files
                    
                    raw_response_text = st.session_state.engine.generate_dossier(
                        st.session_state.gemini_files, 
                        user_text, 
                        mode,
                        PERSONAS[mode],
                        use_external=use_external,
                        status_callback=gen_status_callback 
                    )
                except Exception as e:
                    generation_error = str(e)
                    
            if generation_error:
                gen_warning_placeholder.empty()
                st.error(f"🛑 AI Engine offline: {generation_error}")
                st.stop()
                
            audio_bytes = None
            
            # --- 1. PARSE NATIVE DICTIONARY (NO REGEX FOR JSON) ---
            try:
                response_dict = json.loads(raw_response_text)
                final_text = response_dict.get("dossier_text", raw_response_text)
                has_graph = response_dict.get("requires_graph", False)
            except json.JSONDecodeError:
                # Absolute fallback if API glitches
                final_text = raw_response_text
                has_graph = False
                response_dict = {}

            if mode == "Commuter Podcast (Audio)":
                st.markdown(final_text)
                audio_fp = text_to_audio(final_text)
                audio_bytes = audio_fp.read()
                st.audio(audio_bytes, format="audio/mp3", autoplay=True)
            else:
                # --- 2. RENDER DYNAMIC PLOTLY IF FLAG IS TRUE ---
                if has_graph:
                    try:
                        c_type = response_dict.get("chart_type", "line")
                        if not c_type: c_type = "line"
                        c_type = c_type.lower()
                        
                        x_data = response_dict.get("x_data", [])
                        y_data = response_dict.get("y_data", [])
                        title = response_dict.get("title", "Data Visualization")
                        labels = {
                            "x": response_dict.get("x_axis_label", "X Axis"), 
                            "y": response_dict.get("y_axis_label", "Y Axis")
                        }
                        
                        if c_type == "bar":
                            fig = px.bar(x=x_data, y=y_data, title=title, labels=labels)
                        elif c_type == "scatter":
                            fig = px.scatter(x=x_data, y=y_data, title=title, labels=labels)
                        else:
                            fig = px.line(x=x_data, y=y_data, title=title, labels=labels)
                            
                        fig.update_layout(template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))
                        st.plotly_chart(fig, use_container_width=True)
                        st.markdown("*(Interactive Graph Generated Above)*")
                    except Exception as e:
                        st.warning(f"⚠️ Graph Render Error: {e}")

                # --- 3. RENDER MARKDOWN TEXT (Intercepting Mermaid safely) ---
                # We dynamically create the triple backticks to avoid markdown parser truncation
                bt = "`" * 3
                mermaid_pattern = rf"{bt}(?:mermaid|graph|flowchart)\s*\n(.*?){bt}"
                mermaid_match = re.search(mermaid_pattern, final_text, re.DOTALL | re.IGNORECASE)

                if mermaid_match:
                    mermaid_code = mermaid_match.group(1).strip()
                    st_mermaid(mermaid_code)
                    final_text = re.sub(mermaid_pattern, "\n*(Visual Roadmap Generated Above)*\n", final_text, flags=re.DOTALL | re.IGNORECASE)

                st.markdown(final_text)
            
            gen_warning_placeholder.empty()
            
            # Save the clean text to chat history
            message_data = {"role": "assistant", "content": final_text}
            if audio_bytes:
                message_data["audio"] = audio_bytes
            st.session_state.messages.append(message_data)