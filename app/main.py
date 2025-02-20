import io
import docx
import fitz  # PyMuPDF for PDF extraction
import pandas as pd
import re
from fastapi import FastAPI, UploadFile, File, HTTPException
from typing import List
from fastapi.responses import FileResponse, HTMLResponse

app = FastAPI(
    title="Resume Ranking API",
    description="Upload job descriptions and resumes for ranking.",
    version="1.0"
)

CSV_FILENAME = "resume_scores.csv"

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

# **Extract Candidate Name**
def extract_candidate_name(text: str) -> str:
    """Extracts the candidate's name from the resume text."""
    name_match = re.search(r"(?i)(?:name[:\s]*)([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)", text)
    return name_match.group(1) if name_match else "Unknown Candidate"

# **Extract Job Criteria from JD**
def extract_criteria(text: str) -> List[str]:
    """Extracts job criteria based on keywords."""
    criteria = []
    for line in text.split("\n"):
        line = line.strip()
        if any(keyword in line.lower() for keyword in ["experience", "certification", "skill", "qualification"]):
            criteria.append(line)

    return criteria if criteria else ["No specific criteria found."]

@app.post("/extract-criteria")
async def extract_criteria_api(file: UploadFile = File(...)):
    """Extracts key criteria from an uploaded job description (PDF or DOCX)."""
    try:
        file_bytes = await file.read()
        file_type = file.content_type

        # Determine file type and extract text
        if file_type == "application/pdf":
            extracted_text = extract_text_from_pdf(file_bytes)
        elif file_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
            extracted_text = extract_text_from_docx(file_bytes)
        else:
            raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")

        if not extracted_text:
            raise HTTPException(status_code=400, detail="No text extracted from the document.")

        criteria = extract_criteria(extracted_text)

        return {"criteria": criteria}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text: {str(e)}")

# **Score Resume Based on Job Criteria**
def score_resume(text: str, skills: List[str], experience: List[str], certifications: List[str], qualifications: List[str]) -> dict:
    """Scores a resume separately for skills, experience, certifications, and qualifications."""
    score_dict = {"Skills Score": 0, "Experience Score": 0, "Certifications Score": 0, "Qualifications Score": 0}

    # Assign scores (0-5) per category
    def score_category(criteria_list):
        return min(sum(text.lower().count(c.lower()) for c in criteria_list), 5)

    score_dict["Skills Score"] = score_category(skills)
    score_dict["Experience Score"] = score_category(experience)
    score_dict["Certifications Score"] = score_category(certifications)
    score_dict["Qualifications Score"] = score_category(qualifications)

    score_dict["Total Score"] = sum(score_dict.values())
    score_dict["Candidate Name"] = extract_candidate_name(text)  # ✅ Re-added Candidate Name Extraction

    return score_dict

@app.post("/rank-resumes")
async def rank_resumes(skills: List[str], experience: List[str], certifications: List[str], qualifications: List[str], files: List[UploadFile] = File(...)):
    """Ranks resumes based on provided job criteria."""
    if not (skills or experience or certifications or qualifications):
        raise HTTPException(status_code=400, detail="At least one category (skills, experience, certifications, qualifications) must be provided.")

    scores = []

    for file in files:
        content = await file.read()
        file_type = file.content_type

        # Extract text from resume
        if file_type == "application/pdf":
            text = extract_text_from_pdf(content)
        elif file_type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"]:
            text = extract_text_from_docx(content)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.filename}")

        if not text:
            raise HTTPException(status_code=400, detail=f"No text extracted from {file.filename}")

        score_data = score_resume(text, skills, experience, certifications, qualifications)
        scores.append(score_data)

    df = pd.DataFrame(scores)
    df.to_csv(CSV_FILENAME, index=False)

    return {
        "message": "Scoring completed!",
        "csv_filename": CSV_FILENAME,
        "download_url": "/download-resume-scores",
        "view_results": "/view-results",
        "scores": scores
    }

# **Styled UI for Resume Ranking Results**
@app.get("/view-results", response_class=HTMLResponse)
async def view_results():
    """Displays the resume scores in a well-styled HTML table."""
    try:
        df = pd.read_csv(CSV_FILENAME)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read CSV: {str(e)}")

    html_table = df.to_html(classes="table table-dark table-bordered table-hover", index=False)

    html_content = f"""
    <html>
    <head>
        <title>Resume Ranking Results</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
        <style>
            body {{
                background-color: #121212;
                color: white;
                font-family: 'Arial', sans-serif;
            }}
            .container {{
                max-width: 1000px;
                margin: auto;
                background: #1e1e1e;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0px 0px 15px rgba(128, 0, 128, 0.5);
                margin-top: 40px;
            }}
            h2 {{
                text-align: center;
                color: #9b59b6;
                font-weight: bold;
                margin-bottom: 20px;
            }}
            .btn-primary {{
                background-color: #9b59b6;
                border: none;
                font-size: 18px;
                padding: 10px 20px;
                display: block;
                width: 250px;
                margin: 20px auto;
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🚀 Resume Ranking Results</h2>
            {html_table}
            <a class="btn btn-primary" href="/download-resume-scores">⬇️ Download CSV</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/download-resume-scores")
async def download_resume_scores():
    """Download the generated resume scores CSV."""
    return FileResponse(CSV_FILENAME, media_type="text/csv", filename=CSV_FILENAME)
