import os
from pathlib import Path
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.config import CONFIG, BASE_DIR, LOGGER
from src.schemas import ComplaintExtraction

def load_prompt_template(filename: str) -> str:
    """Reads external prompt files from the prompts/ directory."""
    prompt_path = BASE_DIR / CONFIG.get("paths", {}).get("prompts_dir", "prompts") / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template missing: {prompt_path}")
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()

def get_llm():
    """Initializes the configured LLM provider."""
    model_cfg = CONFIG.get("model", {})
    provider = model_cfg.get("provider", "openai").lower()
    model_name = model_cfg.get("model_name", "gpt-4o-mini")
    temperature = model_cfg.get("temperature", 0.1)

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key
        )

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set.")
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=api_key
        )

    else:
        raise ValueError(f"Unsupported model provider: {provider}")

class ComplaintProcessingChains:
    def __init__(self):
        self.llm = get_llm()
        LOGGER.info(f"Initialized LLM ({CONFIG['model']['provider']} - {CONFIG['model']['model_name']})")
        
        # 1. Extraction Chain with Structured Output
        extraction_template = load_prompt_template("extraction_prompt.txt")
        self.extraction_prompt = PromptTemplate(
            template=extraction_template,
            input_variables=["document_text"]
        )
        self.extraction_chain = (
            self.extraction_prompt | self.llm.with_structured_output(ComplaintExtraction)
        )

        # 2. Customer Email Chain
        email_template = load_prompt_template("customer_email_prompt.txt")
        self.email_prompt = PromptTemplate(
            template=email_template,
            input_variables=[
                "customer_name",
                "complaint_category",
                "issue_description",
                "resolution_provided",
                "case_status"
            ]
        )
        self.email_chain = self.email_prompt | self.llm | StrOutputParser()

        # 3. Case Summary Chain
        summary_template = load_prompt_template("case_summary_prompt.txt")
        self.summary_prompt = PromptTemplate(
            template=summary_template,
            input_variables=[
                "customer_name",
                "complaint_category",
                "escalation_required",
                "case_status",
                "issue_description",
                "document_text"
            ]
        )
        self.summary_chain = self.summary_prompt | self.llm | StrOutputParser()

    def run_extraction(self, document_text: str) -> ComplaintExtraction:
        return self.extraction_chain.invoke({"document_text": document_text})

    def run_email_generation(self, extracted: ComplaintExtraction) -> str:
        return self.email_chain.invoke({
            "customer_name": extracted.customer_name,
            "complaint_category": extracted.complaint_category,
            "issue_description": extracted.issue_description,
            "resolution_provided": extracted.resolution_provided or "Under review by support",
            "case_status": extracted.case_status
        })

    def run_summary_generation(self, extracted: ComplaintExtraction, document_text: str) -> str:
        return self.summary_chain.invoke({
            "customer_name": extracted.customer_name,
            "complaint_category": extracted.complaint_category,
            "escalation_required": "Yes" if extracted.escalation_required else "No",
            "case_status": extracted.case_status,
            "issue_description": extracted.issue_description,
            "document_text": document_text
        })