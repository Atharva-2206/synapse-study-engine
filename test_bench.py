import os
import time
from src.engine import SynapseEngine
from src.utils import process_file
from dotenv import load_dotenv

load_dotenv()

class RAGEvaluator:
    def __init__(self):
        print("Initializing Synapse Test Bench...")
        self.engine = SynapseEngine()
        self.client = self.engine.client
        self.model = "gemini-2.5-flash"

    def rate_limited_call(self, func, *args, **kwargs):
        """A wrapper to handle 429 Rate Limits gracefully."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Add a baseline delay to avoid hitting the 15 Requests Per Minute limit
                time.sleep(4) 
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    wait_time = 50 * (attempt + 1)
                    print(f"    [!] Gemini Free-Tier Rate Limit Hit. Pausing for {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"    [!] Unexpected API Error: {error_msg}")
                    return None
        return None

    def llm_as_a_judge(self, metric, prompt):
        """Uses Gemini to score the outputs from 0.0 to 1.0"""
        judge_system_prompt = f"""
        You are an impartial AI judge evaluating a RAG (Retrieval-Augmented Generation) system.
        You will evaluate the system on: {metric}.
        Output ONLY a single float number between 0.0 and 1.0 representing the score. No other text.
        """
        
        def _make_call():
            response = self.client.models.generate_content(
                model=self.model,
                contents=[judge_system_prompt, prompt]
            )
            return float(response.text.strip())
            
        result = self.rate_limited_call(_make_call)
        return result if result is not None else 0.0

    def calculate_faithfulness(self, context, answer):
        """Proxy for Precision: Is the answer hallucination-free based ON THE CONTEXT?"""
        prompt = f"Context: {context}\n\nGenerated Answer: {answer}\n\nScore 1.0 if the answer is entirely supported by the context. Score 0.0 if the answer hallucinates information not present in the context. Score 0.5 for partial."
        return self.llm_as_a_judge("Faithfulness", prompt)

    def calculate_relevance(self, question, answer):
        """Does the answer actually address the user's prompt?"""
        prompt = f"Question: {question}\n\nGenerated Answer: {answer}\n\nScore 1.0 if the answer perfectly and directly answers the question. Score 0.0 if it is totally irrelevant."
        return self.llm_as_a_judge("Answer Relevance", prompt)

    def run_test_suite(self, test_file_path, test_cases):
        print(f"\n--- 🧪 RUNNING FORMAL RAG EVALUATION ---")
        print(f"File: {test_file_path}\n")
        
        # 1. Setup Phase
        self.engine.clear_context()
        raw_text = process_file(test_file_path)
        self.engine.ingest_local_context(raw_text)
        
        # We will test without the Gemini File API visual context to strictly test ChromaDB retrieval
        gemini_files = [] 
        
        total_faithfulness = 0
        total_relevance = 0

        # 2. Testing Phase
        for i, case in enumerate(test_cases):
            question = case["question"]
            print(f"Test {i+1}: '{question}'")
            
            # Retrieve Context (ChromaDB)
            results = self.engine.collection.query(query_texts=[question], n_results=3)
            retrieved_context = "\n".join(results['documents'][0]) if results['documents'] else ""
            
            # Generate Answer (Wrapped in rate-limit handler)
            def _generate_dossier():
                return self.engine.generate_dossier(
                    gemini_files, 
                    question, 
                    persona_prompt="You are a helpful assistant. Answer strictly based on the provided context.",
                    use_external=False
                )
                
            answer = self.rate_limited_call(_generate_dossier)
            if not answer:
                answer = "Failed to generate due to API errors."
            
            # Evaluate
            faith_score = self.calculate_faithfulness(retrieved_context, answer)
            rel_score = self.calculate_relevance(question, answer)
            
            total_faithfulness += faith_score
            total_relevance += rel_score
            
            print(f"  ↳ Faithfulness (Precision Proxy): {faith_score:.2f}")
            print(f"  ↳ Answer Relevance:               {rel_score:.2f}\n")

        # 3. Report Phase
        avg_faith = total_faithfulness / len(test_cases)
        avg_rel = total_relevance / len(test_cases)
        
        print(f"=====================================")
        print(f"🏆 FINAL EVALUATION METRICS")
        print(f"=====================================")
        print(f"Total Tests Run: {len(test_cases)}")
        print(f"Average Faithfulness: {avg_faith:.2f} / 1.0")
        print(f"Average Relevance:    {avg_rel:.2f} / 1.0")
        
        # Create a faux F1 Score (Harmonic mean of Faithfulness and Relevance)
        if (avg_faith + avg_rel) > 0:
            f1_proxy = 2 * (avg_faith * avg_rel) / (avg_faith + avg_rel)
            print(f"RAG F1-Score Proxy:   {f1_proxy:.2f} / 1.0")
        else:
            print("RAG F1-Score Proxy:   0.00 / 1.0")
        print(f"=====================================")


if __name__ == "__main__":
    # INSTRUCTIONS: Create a simple text file named "test_doc.txt" in your data folder 
    # with a few paragraphs of facts to test against.
    
    # 1. Provide a path to a test document
    test_document = "data/test_doc.txt" 
    
    # Create the test file if it doesn't exist
    if not os.path.exists("data"): os.makedirs("data")
    if not os.path.exists(test_document):
        with open(test_document, "w") as f:
            f.write("Synapse is an AI EdTech tool built in 2024. It uses Gemini 2.5 Flash and ChromaDB to help students learn. The tool features personas like Commuter Podcast and Sprint Mode.")
            
    # 2. Define test questions
    questions = [
        {"question": "What models does Synapse use?"},
        {"question": "What year was Synapse built?"},
        {"question": "What personas are available?"}
    ]
    
    evaluator = RAGEvaluator()
    evaluator.run_test_suite(test_document, questions)