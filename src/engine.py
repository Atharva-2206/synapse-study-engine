import os
import time
from google import genai
from exa_py import Exa
from dotenv import load_dotenv
import chromadb

load_dotenv()

class SynapseEngine:
    def __init__(self):
        # Clients
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        self.exa = Exa(api_key=os.getenv("EXA_API_KEY"))
        
        # Vector Store
        self.db = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.db.get_or_create_collection("study_material")
        
        # Using Gemini 2.0 Flash for Native Multimodal & File API
        self.model_id = "gemini-2.5-flash"

    def upload_to_gemini(self, file_path, mime_type="application/pdf"):
        """Natively uploads file to Gemini File API for visual context."""
        file = self.client.files.upload(file=file_path, config={'mime_type': mime_type})
        
        # Poll until the file is 'ACTIVE' (ready to use)
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
        # We use a 'prompt-engineered' search query for Exa
        search_query = f"Here is a simple, real-world analogy to explain {technical_term} to a student:"
        
        try:
            # use_autoprompt transforms our query into a high-quality neural search
            results = self.exa.search_and_contents(
                search_query,
                type="neural",
                use_autoprompt=True,
                num_results=1,
                text=True, # We want the text content to inject into the LLM
                highlights=True # Gets the most relevant snippet
            )
            
            if results.results:
                best_match = results.results[0]
                return f"Source: {best_match.url}\nContent: {best_match.text[:1500]}" # Limit context window
        except Exception as e:
            return f"Exa Search Error: {str(e)}"
        
        return "No external analogy found."

    def ingest_local_context(self, text):
        """
        Chunks the text and stores it in ChromaDB.
        This allows the 'Local Context' pillar of the Dossier to work.
        """
        # 1. Simple chunking: Split by double newlines (paragraphs)
        # Sliding window chunking
        chunk_size = 1000
        overlap = 200
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += (chunk_size - overlap)
            
        if not chunks: return
        ids = [f"id_{int(time.time())}_{i}" for i in range(len(chunks))]
        self.collection.add(documents=chunks, ids=ids)
            
        # 2. Create unique IDs for these chunks
        ids = [f"id_{int(time.time())}_{i}" for i in range(len(chunks))]
        
        # 3. Add to ChromaDB
        try:
            self.collection.add(
                documents=chunks,
                ids=ids
            )
        except Exception as e:
            print(f"ChromaDB Error: {e}")

    def generate_dossier(self, gemini_file, user_query, persona_prompt, use_external=False):
        """Synthesizes File API, ChromaDB, and Exa.ai into a Study Dossier."""
        
        # 1. RAG: Retrieve the most relevant 3 snippets from ChromaDB
        results = self.collection.query(query_texts=[user_query], n_results=3)
        local_context = "\n".join(results['documents'][0]) if results['documents'] else ""

        # 2. CONDITIONAL ROUTING: Only use Exa.ai if mode is 'Deep Study'
        external_context = ""
        if use_external:
            try:
                # Identify technical anchor
                term_response = self.client.models.generate_content(
                    model=self.model_id,
                    contents=[f"Identify the primary technical concept in this query: {user_query}"]
                )
                tech_term = term_response.text.strip()
                external_context = self.get_web_explainer(tech_term)
            except Exception as e:
                external_context = f"Neural search unavailable: {str(e)}"

        # 3. CONSTRUCT MULTIMODAL PROMPT (With formatting mandates)
        system_instruction = f"""
        {persona_prompt}
        
        ---
        STRICT FORMATTING RULES:
        - DENSITY: Use aggressive whitespace. Use blocks for LaTeX formatted equations
        - SEPARATION: Use '---' horizontal rules between major sections.
        - MATH: Use LaTeX for ALL formulas ($...$). 
        
        MERMAID DIAGRAM RULES (CRITICAL):
        1. Always start with 'flowchart TD'.
        2. EVERY node label MUST be in double quotes to avoid syntax errors. 
           Example: A["f : S -> S"] --> B["Fixed Point Found"]
        3. DO NOT use math symbols like '∘', '→', or LaTeX inside Mermaid labels. Use plain text only (e.g., "f composed with f" instead of "f ∘ f").
        
        VISUAL ENGINE RULES:
        - ROADMAPS: Use ```mermaid code blocks.
        - GRAPHS: Use ```python_plotly code blocks.
        ---
        
        SOURCES:
        1. Visual: The attached PDF layout.
        2. Local: {local_context}
        3. Web: {external_context}
        """

        # 4. GENERATE
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=[gemini_file, system_instruction, user_query]
        )
        
        return response.text