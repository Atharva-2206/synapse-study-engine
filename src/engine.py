import os
import time
from google import genai
from exa_py import Exa
from dotenv import load_dotenv
import chromadb

load_dotenv()

class SynapseEngine:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        self.exa = Exa(api_key=os.getenv("EXA_API_KEY"))
        
        self.db = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.db.get_or_create_collection("study_material")
        
        # Using Gemini 2.5 Flash for Native Multimodal & File API
        self.model_id = "gemini-2.5-flash"

    def clear_context(self):
        """Safely clears all documents by deleting and recreating the ChromaDB collection."""
        try:
            self.db.delete_collection("study_material")
        except Exception:
            pass 
        self.collection = self.db.get_or_create_collection("study_material")

    def upload_to_gemini(self, file_path):
        """Natively uploads file to Gemini File API for context."""
        file = self.client.files.upload(file=file_path)
        
        while file.state.name != "ACTIVE":
            if file.state.name == "FAILED":
                raise Exception("Gemini File Processing Failed.")
            time.sleep(2)
            file = self.client.files.get(name=file.name)
            
        return file

    def get_web_explainer(self, technical_term):
        """
        The Explainer Engine: Using Exa.ai Neural Search.
        Exa finds pages that 'feel' like a simple explanation/analogy.
        """
        search_query = f"Here is a simple, real-world analogy to explain {technical_term} to a student:"
        
        try:
            results = self.exa.search_and_contents(
                search_query,
                type="neural",
                use_autoprompt=True,
                num_results=1,
                text=True, 
                highlights=True 
            )
            
            if results.results:
                best_match = results.results[0]
                return f"Source: {best_match.url}\nContent: {best_match.text[:1500]}"
        except Exception as e:
            return f"Exa Search Error: {str(e)}"
        
        return "No external analogy found."

    def ingest_local_context(self, text):
        """
        Chunks the text and stores it in ChromaDB.
        """
        if not text.strip(): return
        
        chunk_size = 1000
        overlap = 200
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += (chunk_size - overlap)
            
        if not chunks: return
        
        ids = [f"id_{int(time.time()*1000)}_{i}" for i in range(len(chunks))]
        
        try:
            self.collection.add(
                documents=chunks,
                ids=ids
            )
        except Exception as e:
            print(f"ChromaDB Error: {e}")

    def generate_dossier(self, gemini_files, user_query, persona_prompt, use_external=False):
        """Synthesizes File API, ChromaDB, and Exa.ai into a Study Dossier."""
        
        local_context = ""
        if self.collection.count() > 0:
            results = self.collection.query(query_texts=[user_query], n_results=3)
            local_context = "\n".join(results['documents'][0]) if results['documents'] else ""

        external_context = ""
        if use_external:
            try:
                term_response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=[f"Identify the primary technical concept in this query: {user_query}"]
                )
                tech_term = term_response.text.strip()
                external_context = self.get_web_explainer(tech_term)
            except Exception as e:
                external_context = f"Neural search unavailable: {str(e)}"

        system_instruction = f"""
        {persona_prompt}
        
        ---
        STRICT FORMATTING RULES:
        - DENSITY: Use aggressive whitespace. Use blocks for LaTeX formatted equations
        - SEPARATION: Use '---' horizontal rules between major sections.
        - MATH: Use LaTeX for ALL formulas ($...$). 
        
        MERMAID DIAGRAM RULES (CRITICAL):
        1. Always start with 'flowchart TD' or 'graph TD'.
        2. EVERY node label MUST be in double quotes to avoid syntax errors. 
           Example: A["f : S -> S"] --> B["Fixed Point Found"]
        3. DO NOT use math symbols like '∘', '→', or LaTeX inside Mermaid labels. Use plain text only (e.g., "f composed with f" instead of "f ∘ f").
        
        VISUAL ENGINE RULES:
        - ROADMAPS: Use ```mermaid code blocks.
        - GRAPHS: Use ```python_plotly code blocks.
        ---
        
        SOURCES:
        1. Visual: The attached files.
        2. Local: {local_context}
        3. Web: {external_context}
        """

        contents = []
        contents.extend(gemini_files)
        contents.append(system_instruction)
        contents.append(user_query)
        
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=contents
        )
        
        return response.text