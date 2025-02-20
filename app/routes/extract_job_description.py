import io
import fitz  # PyMuPDF for PDF extraction
import docx
import os
import google.generativeai as genai  # ✅ Google Gemini API
from fastapi import FastAPI, UploadFile, File, HTTPException
from typing import List

app = FastAPI()

# ✅ Set Google API Key
GOOGLE_API_KEY = os.getenv("AIzaSyBPje4mrSr0YfllJUAcoHrqP4rCmNph-Vo")  # Secure API key handling
if not GOOGLE_API_KEY:
    raise ValueError("Google API Key not found. Set the GOOGLE_API_KEY environment variable.")
genai.configure(api_key=GOOGLE_API_KEY)

# **Extract Text from PDF**
def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extracts text from a PDF file."""
    try:
        pdf_stream = io.BytesIO(pdf_bytes)
        doc = fitz.open(stream=pdf_stream, filetype="pdf")
        return "\n".join([page.get_text("text") for page in doc]).strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text from PDF: {str(e)}")

# **Extract Text from DOCX**
def extract_text_from_docx(docx_bytes: bytes) -> str:
    """Extracts text from a DOCX file."""
    try:
        doc = docx.Document(io.BytesIO(docx_bytes))
        return "\n".join([para.text.strip() for para in doc.paragraphs if para.text.strip()])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text from DOCX: {str(e)}")

# **Extract Criteria Using Google Gemini API**
def extract_criteria_with_gemini(text: str) -> List[str]:
    """Uses Google's Gemini API to extract key hiring criteria from job descriptions."""
    try:
        prompt = f"""
        Extract and list the key hiring criteria from the following job description.
        Focus on required skills, experience, certifications, and qualifications.

        Job Description:
        {text}

        Return the criteria in a JSON array format like this:
        {{
            "criteria": [
                "Must have certification XYZ",
                "5+ years of experience in Python development",
                "Strong background in Machine Learning"
            ]
        }}
        """

        model = genai.GenerativeModel("gemini-pro")  # ✅ Use Google's Gemini AI
        response = model.generate_content(prompt)

        # ✅ Extract response as JSON
        criteria_data = response.text.strip()

        # ✅ Convert the response to a Python dictionary & return as a list
        return eval(criteria_data).get("criteria", [])

    except Exception as e:
        print(f"Google Gemini Extraction Error: {str(e)}")
        return ["Failed to extract criteria"]

@app.post("/extract-criteria")
async def extract_criteria_api(file: UploadFile = File(...)):
    """Extracts job criteria using Google Gemini API from a job description (PDF or DOCX)."""
    try:
        print(f"Received file: {file.filename}, Content Type: {file.content_type}")

        # ✅ Read file content
        file_bytes = await file.read()
        file_type = file.content_type

        # ✅ Determine file type and extract text
        if file_type == "application/pdf":
            extracted_text = extract_text_from_pdf(file_bytes)
        elif file_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
            extracted_text = extract_text_from_docx(file_bytes)
        else:
            raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")

        if not extracted_text:
            raise HTTPException(status_code=400, detail="No text extracted from the document.")

        # ✅ Extract criteria using Google Gemini AI
        criteria = extract_criteria_with_gemini(extracted_text)

        return {"criteria": criteria}  # ✅ Returns the correct JSON format

    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to extract text: {str(e)}")
