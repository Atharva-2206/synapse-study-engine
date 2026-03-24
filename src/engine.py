import os
import time
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional
from exa_py import Exa
from dotenv import load_dotenv
import chromadb

load_dotenv()

# --- DETERMINISTIC STRUCTURED OUTPUT SCHEMA ---
class SynapseResponse(BaseModel):
    dossier_text: str = Field(description="The full Markdown formatted explanation, including LaTeX equations and Mermaid blocks.")
    requires_graph: bool = Field(description="Set to true if a data visualization is needed based on the context.")
    chart_type: Optional[str] = Field(None, description="'line', 'bar', or 'scatter'")
    title: Optional[str] = Field(None, description="Title of the chart")
    x_axis_label: Optional[str] = Field(None, description="X axis label")
    y_axis_label: Optional[str] = Field(None, description="Y axis label")
    x_data: Optional[list[str]] = Field(None, description="X axis data points (categories or stringified numbers)")
    y_data: Optional[list[float]] = Field(None, description="Y axis data points (strict numeric)")

class SynapseEngine:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        self.exa = Exa(api_key=os.getenv("EXA_API_KEY"))
        self.db = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.db.get_or_create_collection("study_material")
        self.model_id = "gemini-2.5-flash"

    def clear_context(self):
        try:
            self.db.delete_collection("study_material")
        except Exception:
            pass 
        self.collection = self.db.get_or_create_collection("study_material")

    def rate_limited_generate(self, contents, config=None, status_callback=None):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self.client.models.generate_content(
                    model=self.model_id,
                    contents=contents,
                    config=config
                )
            except Exception as e:
                error_msg = str(e)
                if "PerDay" in error_msg or "GenerateRequestsPerDay" in error_msg:
                    raise Exception("Daily API quota exhausted. Please come back tomorrow!")
                elif "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    wait_time = 45 * (attempt + 1)
                    if status_callback:
                        status_callback(f"Gemini Free-Tier Rate Limit Hit. Pausing for {wait_time}s to recover...")
                    time.sleep(wait_time)
                else:
                    raise e 
        raise Exception("Failed after maximum retries due to rate limits.")

    def upload_to_gemini(self, file_path, status_callback=None):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                file = self.client.files.upload(file=file_path)
                while file.state.name != "ACTIVE":
                    if file.state.name == "FAILED":
                        raise Exception("Gemini File Processing Failed.")
                    time.sleep(2)
                    file = self.client.files.get(name=file.name)
                return file
            except Exception as e:
                error_msg = str(e)
                if "PerDay" in error_msg or "GenerateRequestsPerDay" in error_msg:
                    raise Exception("Daily upload quota exhausted.")
                elif "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    wait_time = 45 * (attempt + 1)
                    if status_callback:
                        status_callback(f"File Upload Limit Hit. Pausing for {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise e
        raise Exception("Failed to upload file after maximum retries.")

    def perform_web_search(self, query, search_type="analogy", status_callback=None):
        if search_type == "analogy":
            search_query = f"Here is a simple, real-world analogy to explain {query} to a student:"
        else:
            search_query = query

        try:
            results = self.exa.search_and_contents(
                search_query, type="neural", use_autoprompt=True,
                num_results=3 if search_type == "factual" else 1, text=True, highlights=True 
            )
            if results.results:
                if search_type == "factual":
                    context = "Web Search Results:\n"
                    for r in results.results:
                        context += f"- Source: {r.url}\n  Content: {r.text[:1000]}\n"
                    return context
                else:
                    best_match = results.results[0]
                    return f"Source: {best_match.url}\nContent: {best_match.text[:1500]}"
        except Exception as e:
            error_msg = str(e).lower()
            if "429" in error_msg or "quota" in error_msg or "limit" in error_msg:
                if status_callback:
                    status_callback("Exa.ai search quota reached. Relying on local memory only.")
                return "External context unavailable (API Quota Exceeded)."
            else:
                return f"Exa Search Error: {str(e)}"
        return "No external context found."

    def ingest_local_context(self, text):
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
            self.collection.add(documents=chunks, ids=ids)
        except Exception as e:
            pass

    def generate_dossier(self, gemini_files, user_query, persona_name, persona_prompt, use_external=False, status_callback=None):
        local_context = ""
        if self.collection.count() > 0:
            results = self.collection.query(query_texts=[user_query], n_results=3)
            local_context = "\n".join(results['documents'][0]) if results['documents'] else ""

        fileless_mode = len(gemini_files) == 0
        external_context = ""

        if use_external or fileless_mode:
            try:
                if fileless_mode or persona_name == "Internet Searcher":
                    if status_callback: status_callback("Searching the web for factual context...")
                    external_context = self.perform_web_search(user_query, search_type="factual", status_callback=status_callback)
                else:
                    if status_callback: status_callback("Extracting technical concepts for web analogy...")
                    term_response = self.rate_limited_generate(
                        contents=[f"Identify the primary technical concept in this query: {user_query}"],
                        status_callback=status_callback
                    )
                    tech_term = term_response.text.strip()
                    external_context = self.perform_web_search(tech_term, search_type="analogy", status_callback=status_callback)
            except Exception:
                external_context = "Neural search unavailable."

        fileless_notice = ""
        if fileless_mode:
            fileless_notice = "\n[CRITICAL SYSTEM NOTICE: NO FILES UPLOADED. Ignore ALL prompt formatting rules demanding 'Extract from PDF'. Answer strictly using your internal knowledge and the Web Context.]\n"

        system_instruction = f"""
        {persona_prompt}
        {fileless_notice}
        ---
        STRICT FORMATTING RULES:
        - DENSITY: Use aggressive whitespace.
        - MATH: Use LaTeX for ALL formulas ($...$). 
        - MERMAID DIAGRAMS: Always start with 'graph TD'. Enclose node labels in double quotes. 
          Example: A["f: S -> S"]
        ---
        SOURCES:
        1. Local: {local_context}
        2. Web: {external_context}
        """

        contents = []
        contents.extend(gemini_files)
        contents.append(system_instruction)
        contents.append(user_query)
        
        # --- PYDANTIC ENFORCEMENT CONFIG ---
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=SynapseResponse,
            temperature=0.2, 
        )
        
        response = self.rate_limited_generate(
            contents=contents, 
            config=config,
            status_callback=status_callback
        )
        
        return response.text