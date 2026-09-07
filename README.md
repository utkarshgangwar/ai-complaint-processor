# ai-complaint-processor
Project for IIT Patna's Certification of GenAI and Agentic AI for developers

This project is an Automated Customer Support Processing Engine that replaces hours of manual paperwork by reading incoming customer documents and instantly producing structured business data, personalized customer replies, and executive briefings.

The Problem It Solves:
Normally, when customers send support complaints via PDF forms, scanned letters, or Word documents, human agents must manually open each file, read through the text, type the details into a database, write an email back to the customer, and brief their manager if something is urgently broken.

This application automates that entire process for batches of documents at the click of a button.

How It Works (Step-by-Step):
1. Document Reading (Ingestion):
- The program looks inside the data/ folder and opens every file, regardless of whether it is a .pdf, .docx (Word), or .txt file.
- It extracts the plain text from the file so the AI can read it.

2. Smart Information Extraction:
- It sends the text to the LLM (like GPT-4o-mini or Gemini) with a strict rulebook called a Pydantic Schema.
- Instead of just chatting, the AI acts like an intelligent form-filler: it extracts exact fields such as the customer's name, contact email, complaint category, core problem, and whether the issue is severe enough to need managerial escalation.
- It saves these details as clean, standardized .json files.

3. Automated Customer Response:
- Using the extracted customer name and issue details, the LLM drafts a polite, empathetic support email ready to be sent to the customer.
- If a solution is already known, it includes it; if the case is still being investigated, it acknowledges the delay professionally without making up fake promises.

4. Internal Management Briefing:
- For the internal support team, the LLM summarizes the issue into a 5-point executive memo covering root causes, current ticket status, and recommended next actions.

5. Consolidation & Dashboard:
- It takes every extracted field from all processed files and stacks them neatly into a single spreadsheet (output/final_report.csv).
- In the Streamlit web dashboard, managers can see live KPI counts (total cases, escalations needed, active tickets), view the full dataset, filter priority cases, and inspect the generated emails and JSON outputs side-by-side.


# AI-Powered Customer Complaint & Document Processing Pipeline

An enterprise-grade, batch-oriented Generative AI workflow built with Python, LangChain, Pydantic, and Streamlit. The system automates ingestion of customer complaint records across multiple file formats, performs schema-enforced structured data extraction, drafts personalized customer resolution emails, generates internal executive briefings, and consolidates all records into an analytics-ready CSV report.

---

## 1. Problem Statement & Solution Architecture

Handling high-volume customer grievances and operational documents manually leads to processing delays, inconsistent escalation handling, and fragmented audit trails. 

This application provides a batch-processing engine that replaces ad-hoc LLM prompting with an orchestrated, multi-stage pipeline:
1. **Multi-Format Ingestion**: Ingests `.pdf`, `.docx`, and `.txt` files directly from a designated `data/` directory with error-tolerant parsers.
2. **Deterministic Extraction**: Employs LangChain's `.with_structured_output()` backed by strict Pydantic schemas to eliminate output hallucinations and guarantee field consistency.
3. **Automated Response Synthesis**: Generates empathetic, contextual resolution emails mapped to the customer and issue.
4. **Management Briefings**: Produces structured internal case summaries highlighting escalation status and root causes.
5. **Consolidation**: Aggregates batch results into a unified `final_report.csv` alongside individual document artifacts.

```
[Local Documents: .pdf, .docx, .txt]
                 │
                 ▼
      [Document Ingestion Layer] (pypdf, python-docx, standard I/O)
                 │
                 ▼
     [Structured Extraction Chain] (LLM + Pydantic Validation Schema)
                 │
        ┌────────┴──────────────────────────┐
        ▼                                   ▼
 [Customer Email Chain]         [Management Summary Chain]
        │                                   │
        └────────┬──────────────────────────┘
                 ▼
      [Persistence & CSV Aggregator] 
      ├── output/structured_data/*.json
      ├── output/customer_emails/*_email.txt
      ├── output/case_summaries/*_summary.txt
      └── output/final_report.csv
                 │
                 ▼
  [Streamlit Interactive Dashboard & Document Inspector]
  ```

## 2. Technology Stack
```
Language: Python 3.10+  
LLM Framework: LangChain (Core, OpenAI, Google-GenAI)  
Data Validation & Typing: Pydantic v2  
Document Parsing: pypdf, python-docx  
Data Aggregation: pandasUser 
Interface: Streamlit  
Configuration Management: pyyaml, python-dotenv
Testing Suite: pytest
```

## 3. Project Structure
```
ai-complaint-processor/
├── config/
│   └── config.yaml                     # Model provider, temperature, and directory configurations
├── data/                               # Input directory for raw complaint documents
├── logs/                               # Auto-created rotating execution traces
│   └── app.log
├── output/                             # Auto-generated pipeline artifacts
│   ├── case_summaries/                 # Generated executive case briefs
│   ├── customer_emails/                # Generated customer-facing draft emails
│   ├── structured_data/                # Validated JSON records per document
│   └── final_report.csv                # Consolidated batch summary spreadsheet
├── prompts/                            # Decoupled system prompt templates
│   ├── case_summary_prompt.txt
│   ├── customer_email_prompt.txt
│   └── extraction_prompt.txt
├── src/
│   ├── __init__.py
│   ├── chains.py                       # LangChain extraction and generation runnables
│   ├── config.py                       # Dynamic path bootstrapping and YAML loaders
│   ├── document_loader.py              # File ingestion handlers (.pdf, .docx, .txt)
│   ├── logger.py                       # Structured rotating logger
│   ├── pipeline.py                     # Batch orchestration engine and CSV aggregator
│   ├── schemas.py                      # Pydantic data contracts
│   └── utils.py                        # File I/O helpers and text cleaners
├── tests/
│   ├── __init__.py
│   ├── test_document_loader.py         # Unit tests for multi-format file ingestion
│   └── test_schemas.py                 # Unit tests for Pydantic data constraints
├── app.py                              # Streamlit dashboard entry point
├── main.py                             # CLI headless batch runner entry point
├── requirements.txt                    # Project dependencies
├── .env.example                        # Template for required environment variables
├── .gitignore                          # Excludes secrets, logs, output artifacts, and caches
└── README.md                           # Documentation and setup instructions
├── Dockerfile                          # Container image definition
├── docker-compose.yml                  # Service orchestration, port mapping & volumes
├── .dockerignore                       # Excludes secrets, venvs, and local caches
```

## 4. Setup & Installation Instructions
PrerequisitesPython 3.10 or higher installed on your system.
An active API key from either OpenAI or Google Gemini.  

Step 1: Clone the Repository
```
git clone <your-repository-url>
cd ai-complaint-processor
```

Step 2: Create and Activate a Virtual Environment
```
# On macOS / Linux:
python3 -m venv venv
source venv/bin/activate

# On Windows (PowerShell):
python -m venv venv
venv\Scripts\Activate.ps1
```

Step 3: Install Required Dependencies
```
pip install --upgrade pip
pip install -r requirements.txt
```

Step 4: Configure Environment Variables
Copy .env.example to .env and insert your API key:
```
cp .env.example .env
```
Inside .env, configure the relevant key:
```
OPENAI_API_KEY="your-actual-openai-key"
# OR if using Google Gemini:
GOOGLE_API_KEY="your-actual-gemini-key"
```

Step 5: Adjust Configuration (Optional)
To switch between OpenAI and Gemini, adjust config/config.yaml:
```
model:
  provider: "openai"          # Options: "openai" or "google"
  model_name: "gpt-4o-mini"   # e.g., "gemini-1.5-flash" for google
  temperature: 0.1
```

## 5. How to Run the Application
### Option A: Launch Interactive Streamlit Dashboard (Recommended)
```
streamlit run app.py
```
Navigate to http://localhost:8501 in your browser.
Upload files (.pdf, .docx, .txt) using the sidebar uploader.
Click Execute Batch Workflow to run the pipeline.
View the aggregated analytics and download final_report.csv in Tab 1.
Inspect structured JSON fields and drafted outputs per document in Tab 2.

### Option B: Headless Execution via CLI
Ensure test documents are placed in data/, then execute:
```
python main.py
```
Outputs will be automatically populated inside the output/ directory.

### Option C: Containerized Execution via Docker & Docker Compose (Recommended for Deployment)

Ensure Docker and Docker Compose are installed, and your `.env` file is created in the project root.

1. **Build and start the container in detached mode:**
   ```bash
   docker compose up -d --build
   ```
2. **Verify running containers and inspect real-time logs:**
   ```bash
   docker compose ps
   docker compose logs -f
   ```
3. Access the application:
    Open http://localhost:8501 (or http://<EC2-PUBLIC-IP>:8501).
4. Stop the container:
   ```bash
   docker compose down
   ```
Data Persistence Note: The docker-compose.yml mounts local ./data, ./output, and ./logs directories as host volumes. Any files uploaded through the UI or generated during pipeline execution automatically persist on your host machine.



## 6. Running Automated Tests
Run the test suite to verify ingestion logic and schema constraints without calling external LLM APIs:
```
pytest tests/ -v
```

## 7. Key Design Decisions
Externalized Prompts: System prompts reside in /prompts as plain text files rather than being hard-coded inside Python strings, facilitating fast prompt tuning without changing code.

Separation of Concerns: Extractor, Email Generator, and Case Summarizer run as isolated LangChain components[cite: 1]. Failures in email formatting do not corrupt structured data extraction.

Dynamic Directory Bootstrapping: src/config.py automatically initializes missing directories (logs/, output/structured_data/, etc.) at runtime, avoiding manual folder setup.

Error Resilience: Files failing ingestion or validation are logged cleanly to logs/app.log without terminating the batch processing of subsequent files.

