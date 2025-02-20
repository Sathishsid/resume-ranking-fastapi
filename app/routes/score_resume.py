from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List, Dict
import google.generativeai as genai
import docx
import pdfplumber
import io
import json

router = APIRouter()

# Initialize Google Gemini Model
genai.configure(api_key="AIzaSyBPje4mrSr0YfllJUAcoHrqP4rCmNph-Vo")  # Replace with your API Key
model = genai.GenerativeModel("gemini-1.5-pro")

def extract_text_from_docx(file_content: bytes) -> str:
    """Extracts text from a DOCX file."""
    doc = docx.Document(io.BytesIO(file_content))
    return "\n".join([para.text.strip() for para in doc.paragraphs if para.text.strip()])

def extract_text_from_pdf(file_content: bytes) -> str:
    """Extracts text from a PDF file."""
    text = ""
    with pdfplumber.open(io.BytesIO(file_content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()

def score_with_gemini(job_description: str, job_criteria: List[str], resume_text: str) -> Dict[str, float]:
    """Uses Google Gemini AI to score the resume against job criteria."""
    try:
        prompt = f"""
        You are an experienced HR professional responsible for evaluating resumes based on job requirements.

        **Job Description**:  
        {job_description}

        **Key Evaluation Criteria**:  
        {', '.join(job_criteria)}

        **Candidate's Resume**:  
        {resume_text}

        ### **Task:**  
        1. Score the resume for each criterion on a scale of **0 to 5**, where:
           - 5 = Perfect match
           - 4 = Strong match
           - 3 = Moderate match
           - 2 = Partial match
           - 1 = Weak match
           - 0 = No match  
        2. Return **ONLY** a JSON response in this format:  
        ```json
        {{
            "skills_score": <score>,
            "experience_score": <score>,
            "certifications_score": <score>,
            "qualifications_score": <score>
        }}
        ```
        """

        response = model.generate_content(prompt)
        scores = json.loads(response.text.strip())

        # Compute total score
        total_score = sum(scores.values())

        return {
            "Skills Score": scores.get("skills_score", 0),
            "Experience Score": scores.get("experience_score", 0),
            "Certifications Score": scores.get("certifications_score", 0),
            "Qualifications Score": scores.get("qualifications_score", 0),
            "Total Score": total_score
        }

    except Exception as e:
        print(f"Google Gemini Scoring Error: {str(e)}")
        return {"Skills Score": 0, "Experience Score": 0, "Certifications Score": 0, "Qualifications Score": 0, "Total Score": 0}

@router.post("/rank-resumes")
async def rank_resumes(job_description: str, job_criteria: List[str], resume: UploadFile = File(...)):
    """Ranks a resume using Google Gemini AI based on job criteria."""
    
    # Validate file type
    if resume.content_type not in ["application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    # Read file content in memory
    content = await resume.read()

    # Extract text based on file type
    if resume.filename.endswith(".docx"):
        resume_text = extract_text_from_docx(content)
    elif resume.filename.endswith(".pdf"):
        resume_text = extract_text_from_pdf(content)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format")

    # Use Google Gemini to score the resume
    ai_scores = score_with_gemini(job_description, job_criteria, resume_text)

    return {
        "resume": resume.filename,
        "scores": ai_scores
    }
