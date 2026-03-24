# **Synapse AI Tutor**

**Synapse** is an adaptive, multimodal AI learning companion designed to break down complex study materials based on your unique learning style. Whether you are an auditory learner commuting to work, a STEM student needing data visualizations, or an ESL student requiring cross-cultural analogies, Synapse dynamically shapes the educational experience for you.

## **Live Demo**

Try the deployed application here: [**Synapse AI Tutor**](https://synapse-ai-student.streamlit.app/)

## **Key Features**

Synapse operates using distinct "Personas", leveraging Retrieval-Augmented Generation (RAG) and the Gemini File API to understand uploaded PDFs, images, and text:

* 🏃 **Sprint Mode (Focus):** Designed for ADHD & quick reviews. Generates fast-paced milestones, Mermaid.js flowcharts, and active-recall challenges.  
* 🎧 **Commuter Podcast (Audio):** Converts complex documents into engaging, conversational audio scripts using text-to-speech (gTTS). Accepts voice prompts\!  
* 🔬 **Deep Study (STEM/Research):** Extracts LaTeX math and dynamically generates interactive **Plotly** data visualizations based on document contexts.  
* 🌍 **Global Scholar (ESL):** Bridges language barriers by using live neural web searches (Exa.ai) to find simple, cross-cultural analogies for high-level concepts.  
* 👁️ **Visual Deconstructor:** Breaks down complex spatial diagrams, charts, and data flows step-by-step for visual learners.  
* 📖 **Critical Analyst (Humanities):** Acts as a Socratic professor, focusing on thematic breakdowns and textual evidence.  
* 🌐 **Internet Searcher:** Bypasses local documents to scour the web for instant, factual answers.

## **Tech Stack**

* **Frontend:** [Streamlit](https://streamlit.io/)  
* **LLM Engine:** Google Gemini 2.5 Flash (via google-genai SDK)  
* **Structured Outputs:** Pydantic (Deterministic JSON generation)  
* **Vector Database:** [ChromaDB](https://www.trychroma.com/) (Local context retrieval)  
* **Web Search:** [Exa.ai](https://exa.ai/) (Neural search for analogies and factual grounding)  
* **Document Ingestion:** PyMuPDF (fitz), MarkItDown, Pillow  
* **Visualization:** Plotly Express, Streamlit-Mermaid

## **Project Structure**

synapse/  
├── app.py                  \# Main Streamlit application UI  
├── requirements.txt        \# Python dependencies  
├── .env                    \# API Keys (Not tracked in Git)  
├── .gitignore              \# Git ignore rules  
├── src/  
│   ├── engine.py           \# Core RAG, GenAI, and Exa search logic  
│   ├── prompts.py          \# System instructions and Persona definitions  
│   └── utils.py            \# Document parsing and Text-to-Speech helpers  
└── test\_bench.py           \# LLM-as-a-judge RAG Evaluator

## **Installation & Setup**

**1\. Clone the repository**

git clone [https://github.com/Atharva-2206/synapse-study-engine.git](https://github.com/Atharva-2206/synapse-study-engine.git)
cd synapse-study-engine

**2\. Install dependencies**

It is recommended to use a virtual environment.

pip install \-r requirements.txt

**3\. Set up Environment Variables**

Create a .env file in the root directory and add your API keys:

GOOGLE\_API\_KEY=your\_gemini\_api\_key\_here  
EXA\_API\_KEY=your\_exa\_api\_key\_here

**4\. Run the Application**

streamlit run app.py

## **RAG Evaluation Suite**

Synapse includes a custom "LLM-as-a-judge" evaluation suite to test the accuracy of the Retrieval-Augmented Generation pipeline. It scores the system on **Faithfulness** (Precision/Hallucination prevention) and **Answer Relevance**.

To run the test suite:

python test\_bench.py

## **License**

This project is for educational and portfolio purposes.
