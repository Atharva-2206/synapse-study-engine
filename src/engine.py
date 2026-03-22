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

    def generate_dossier(self, gemini_file, user_query, persona_prompt):
        """Synthesizes File API, ChromaDB, and Exa.ai into a Study Dossier."""
        
        # 1. RAG: Retrieve local semantic context
        results = self.collection.query(query_texts=[user_query], n_results=3)
        local_context = "\n".join(results['documents'][0]) if results['documents'] else ""

        # 2. TRIGGER EXPLAINER ENGINE (For Global Scholar or Deep Study)
        external_context = ""
        # We ask Gemini to identify the 'technical anchor' first
        term_response = self.client.models.generate_content(
            model=self.model_id,
            contents=[f"Identify the primary technical concept in this query for a search engine: {user_query}"]
        )
        tech_term = term_response.text.strip()
        external_context = self.get_web_explainer(tech_term)

        # 3. CONSTRUCT MULTIMODAL PROMPT
        system_instruction = f"""
        {persona_prompt}
        
        Your analysis must combine:
        1. VISUAL CONTEXT: The layout/charts in the attached PDF.
        2. LOCAL CONTEXT: Key snippets from the textbook: {local_context}
        3. EXTERNAL CONTEXT: A simplified real-world analogy found via neural search: {external_context}
        
        Return a 'Study Dossier' that is structured, clear, and reduces cognitive load.
        """

        # 4. GENERATE
        response = self.client.models.generate_content(
            model=self.model_id,
            contents=[gemini_file, system_instruction, user_query]
        )
        
        return response.text