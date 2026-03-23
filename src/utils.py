import fitz
from PIL import Image
from gtts import gTTS
import io
import os

def process_pdf(uploaded_file):
    """Extracts text from ALL pages for RAG."""
    file_bytes = uploaded_file.read()
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    
    # Extract text from ALL pages
    full_text = ""
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        full_text += page.get_text() + "\n\n"
        
    return full_text, None # We don't need the PIL image anymore since app.py uploads the raw PDF buffer to Gemini
    
    

def text_to_audio(text):
    """Converts response text to speech for Commuter Mode."""
    # Clean text of markdown characters for better speech
    clean_text = text.replace("*", "").replace("#", "").replace("-", " ")
    tts = gTTS(text=clean_text[:500], lang='en') # Limit to 500 chars for speed
    audio_fp = io.BytesIO()
    tts.write_to_fp(audio_fp)
    return audio_fp