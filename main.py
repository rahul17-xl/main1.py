import os
import uuid
import io
from datetime import datetime
from typing import List, Optional, Literal
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pypdf import PdfReader
from openai import OpenAI

# Initialize FastAPI
app = FastAPI(title="IntellifyAI Document Extraction Engine")

# Enable CORS so our frontend can talk to our backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "your-openai-key-here"))

# --- DATA SCHEMAS & VALIDATION ---
ConfidenceLiteral = Literal["high", "medium", "low"]

class FieldWithConfidence(BaseModel):
    value: Optional[str] = Field(None, description="The extracted text value. Return null if missing.")
    confidence: ConfidenceLiteral = Field(..., description="High, medium, or low based on visual clarity.")

class InvoiceSchema(BaseModel):
    vendor: FieldWithConfidence
    date: FieldWithConfidence
    total_amount: FieldWithConfidence
    line_items: Optional[List[str]] = Field(default=[], description="List of items or descriptions bought.")
    missing_fields_note: Optional[str] = Field(None, description="Note explicitly if any required fields are missing.")

class ResumeSchema(BaseModel):
    candidate_name: FieldWithConfidence
    skills: List[str] = Field(default=[], description="List of technical or professional skills found.")
    experience: Optional[str] = Field(None, description="Summary of past employment history.")
    education: Optional[str] = Field(None, description="Degrees, certifications, or colleges attended.")
    missing_fields_note: Optional[str] = Field(None, description="Note explicitly if any required fields are missing.")

# In-memory storage mock database
EXTRACTION_DB = {}

# --- API ENDPOINTS ---
@app.post("/extract")
async def extract_document(file: UploadFile = File(...), document_type: str = Form(...)):
    filename = file.filename.lower()
    if not (filename.endswith('.pdf') or filename.endswith('.txt')):
        raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF or TXT.")

    try:
        # Extract Raw Text
        raw_text = ""
        contents = await file.read()
        
        if filename.endswith('.pdf'):
            pdf_file = io.BytesIO(contents)
            reader = PdfReader(pdf_file)
            for page in reader.pages:
                raw_text += page.extract_text() or ""
        else:
            raw_text = contents.decode("utf-8")

        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="The uploaded file contains no extractable text.")

        # Determine target validation schema
        target_schema = InvoiceSchema if document_type.lower() == "invoice" else ResumeSchema
        
        system_prompt = (
            "You are an expert document extraction engine. Extract raw information into strict structured JSON.\n"
            "CRITICAL RULES:\n"
            "1. Never hallucinate or make up any values.\n"
            "2. If a field is not present explicitly in the text, return null for the value.\n"
            "3. Grade confidence as high, medium, or low based on presence."
        )

        # Call OpenAI Structured Outputs Parse Method
        completion = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract data from this text:\n\n{raw_text}"}
            ],
            response_format=target_schema,
        )
        
        extracted_json = completion.choices[0].message.parsed

        # Save record log metadata
        record_id = str(uuid.uuid4())
        record = {
            "id": record_id,
            "filename": file.filename,
            "type": document_type,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "result": extracted_json.model_dump()
        }
        EXTRACTION_DB[record_id] = record
        return record

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

@app.get("/extractions")
def list_extractions():
    return [
        {"id": v["id"], "filename": v["filename"], "type": v["type"], "timestamp": v["timestamp"]}
        for v in EXTRACTION_DB.values()
    ]

@app.get("/extractions/{id}")
def get_extraction(id: str):
    if id not in EXTRACTION_DB:
        raise HTTPException(status_code=404, detail="Extraction record not found.")
    return EXTRACTION_DB[id]
