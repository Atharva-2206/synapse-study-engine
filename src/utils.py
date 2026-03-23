import fitz
from gtts import gTTS
import io
import os
from markitdown import MarkItDown

def process_file(file_path):
    """Universal file ingestion for RAG text extraction."""
    ext = os.path.splitext(file_path)[1].lower()
    full_text = ""
    
    if ext == '.pdf':
        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            full_text += page.get_text() + "\n\n"
    elif ext in ['.png', '.jpg', '.jpeg', '.heic']:
        # Images don't have natively extractable text without OCR, 
        # but I rely on Gemini's File API for their visual context directly.
        full_text = ""
    else:
        try:
            md = MarkItDown()
            result = md.convert(file_path)
            full_text = result.text_content
        except Exception as e:
            print(f"MarkItDown Error processing {file_path}: {e}")
            full_text = ""
            
    return full_text

def text_to_audio(text):
    """Converts response text to speech for Commuter Mode."""
    clean_text = text.replace("*", "").replace("#", "").replace("-", " ").replace("`", "")
    
    tts = gTTS(text=clean_text, lang='en') 
    
    audio_fp = io.BytesIO()
    tts.write_to_fp(audio_fp)
    audio_fp.seek(0) 
    
    return audio_fp