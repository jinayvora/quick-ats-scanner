"""
Quick ATS Matcher, Cover Letter & Outreach Generator
A lightweight, fast, single-page application.
"""

import io
import json
import os
from typing import Optional

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from pypdf import PdfReader
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from fpdf import FPDF

# Initialize App
app = FastAPI(title="Quick ATS Matcher")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = "openai/gpt-4o-mini"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class AnalysisRequest(BaseModel):
    resume_text: str
    job_description: str
    api_key: Optional[str] = None


class DownloadCoverLetterRequest(BaseModel):
    content: str
    filename: Optional[str] = "Cover_Letter"


async def call_llm(system_prompt: str, user_prompt: str, json_mode: bool = False, api_key: Optional[str] = None) -> str:
    key = api_key.strip() if api_key and api_key.strip() else OPENROUTER_API_KEY
    if not key:
        raise HTTPException(
            status_code=400,
            detail="No OpenRouter API key found. Please set OPENROUTER_API_KEY or provide it in the UI."
        )

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5050",
        "X-Title": "Quick ATS Matcher",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to connect to AI provider: {str(e)}")

        if resp.status_code != 200:
            err_msg = resp.text
            try:
                err_data = resp.json()
                err_msg = err_data.get("error", {}).get("message", resp.text)
            except Exception:
                pass
            raise HTTPException(status_code=resp.status_code, detail=f"AI Error: {err_msg}")

        data = resp.json()
        return data["choices"][0]["message"]["content"]


@app.post("/api/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)):
    """Extract text from an uploaded resume PDF."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    try:
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join([page.extract_text() or "" for page in reader.pages])
        if not text.strip():
            raise HTTPException(status_code=422, detail="Could not extract text from this PDF (it might be scanned).")
        return {"filename": file.filename, "text": text.strip()}
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to read PDF: {str(e)}")


@app.post("/api/calculate-ats")
async def calculate_ats(req: AnalysisRequest):
    """Analyze Resume against Job Description and return a comprehensive ATS report."""
    if not req.resume_text.strip() or not req.job_description.strip():
        raise HTTPException(status_code=400, detail="Both Resume and Job Description are required.")

    system_prompt = """You are an Objective Enterprise ATS Parsing & Scoring Engine (simulating systems like Workday, Taleo, Greenhouse, and iCIMS).

Calculate mathematically grounded ATS scores without anchor bias or arbitrary penalties.
Follow these exact scoring formulas:

1. KEYWORD MATCH (weight: 40%):
   - Extract all core keywords, technologies, tools, and methodologies required or emphasized in the Job Description.
   - Count how many appear in the Resume (verbatim or direct synonyms).
   - keyword_match = round((matched_keywords_count / max(1, total_jd_keywords_count)) * 100)

2. SKILLS COVERAGE (weight: 25%):
   - Identify the critical hard skills/competencies required by the JD.
   - Count how many are demonstrated in the candidate's skills list or work experience.
   - skills_coverage = round((matched_skills_count / max(1, required_skills_count)) * 100)
   - If candidate covers all core technical skills, this MUST score 95-100%.

3. EXPERIENCE MATCH (weight: 20%):
   - Check years of experience and seniority level requested in JD versus shown in resume.
   - If candidate meets or exceeds the required years/seniority: score 95-100%.
   - If candidate has 4 years and JD asks for 5 years: score round((4 / 5) * 100) = 80%.
   - If candidate has significantly fewer years: score proportionally.

4. JOB TITLE MATCH (weight: 15%):
   - If candidate's headline or current/recent job title directly matches target title: score 100%.
   - If closely synonymous (e.g. "Senior Platform Engineer" vs "Senior DevOps Engineer", or "Frontend Engineer" vs "React Developer"): score 85-90%.
   - If related but lower seniority (e.g. "DevOps Engineer" vs "Senior DevOps Engineer"): score 75-80%.
   - If unrelated: score 40-50%.

5. OVERALL SCORE:
   - Compute EXACTLY: round(0.40 * keyword_match + 0.25 * skills_coverage + 0.20 * experience_match + 0.15 * job_title_match)
   - Verdict: >= 80% is "Interview Likely", 60-79% is "Application at Risk", < 60% is "High Rejection Probability".

Respond with ONLY valid JSON with this exact schema (do not anchor to any predetermined numbers):
{
  "overall_score": <computed integer from formula 0-100>,
  "verdict": "<Interview Likely | Application at Risk | High Rejection Probability>",
  "summary": "<2-3 sentences explaining the factual match alignment>",
  "sub_scores": {
    "keyword_match": <computed integer 0-100>,
    "skills_coverage": <computed integer 0-100>,
    "experience_match": <computed integer 0-100>,
    "job_title_match": <computed integer 0-100>
  },
  "sub_score_details": {
    "keywords": {
      "score": <same as keyword_match>,
      "what_affected_it": "<State exactly how many keywords were found out of total, which matched, and which missed>",
      "how_to_improve": "<Exact keywords to add into experience bullets to reach 95-100%>"
    },
    "skills": {
      "score": <same as skills_coverage>,
      "what_affected_it": "<Specific required skills covered vs any missing critical hard skills>",
      "how_to_improve": "<Exact skills to explicitly add to the Technical Skills section>"
    },
    "experience": {
      "score": <same as experience_match>,
      "what_affected_it": "<Candidate years and seniority vs JD requested years and scale requirements>",
      "how_to_improve": "<How to highlight metrics, production scale, or leadership to maximize score>"
    },
    "job_title": {
      "score": <same as job_title_match>,
      "what_affected_it": "<How candidate's target title and past titles align with target posting title>",
      "how_to_improve": "<Exact title or headline adjustment needed to achieve 100%>"
    }
  },
  "matched_keywords": ["list", "of", "all", "matched", "terms"],
  "missing_keywords": ["list", "of", "all", "missing", "terms"],
  "recommendations": [
    "High-impact actionable recommendation 1",
    "High-impact actionable recommendation 2",
    "High-impact actionable recommendation 3"
  ]
}"""

    user_prompt = f"""--- CANDIDATE RESUME ---
{req.resume_text}

--- TARGET JOB DESCRIPTION ---
{req.job_description}"""

    result_text = await call_llm(system_prompt, user_prompt, json_mode=True, api_key=req.api_key)
    try:
        data = json.loads(result_text)
        
        # Enforce exact mathematical consistency in Python (never trust LLM arithmetic)
        sub = data.get("sub_scores", {})
        kw = float(sub.get("keyword_match", 0))
        sk = float(sub.get("skills_coverage", 0))
        exp = float(sub.get("experience_match", 0))
        tm = float(sub.get("job_title_match", 0))

        # True weighted average: Keywords 40%, Skills 25%, Experience 20%, Title 15%
        calculated_overall = round(0.40 * kw + 0.25 * sk + 0.20 * exp + 0.15 * tm)
        data["overall_score"] = calculated_overall

        # Accurate verdict based on mathematically validated score
        if calculated_overall >= 80:
            data["verdict"] = "Interview Likely"
        elif calculated_overall >= 60:
            data["verdict"] = "Application at Risk"
        else:
            data["verdict"] = "High Rejection Probability"

        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse ATS response: {str(e)}")


@app.post("/api/generate-cover-letter")
async def generate_cover_letter(req: AnalysisRequest):
    """Generate a tailored, high-converting cover letter based on Resume and JD."""
    if not req.resume_text.strip() or not req.job_description.strip():
        raise HTTPException(status_code=400, detail="Both Resume and Job Description are required.")

    system_prompt = """You are an expert tech hiring manager and career coach.
Write a high-impact, modern cover letter for a candidate applying directly to the specified open job.

STRICT FORMATTING & STYLE RULES:
- NO postal letterhead or fake placeholders (do NOT write "[Your Address]", "[City, State, Zip]", "[Company Address]", "[Date]").
- Begin directly with: "Dear Hiring Team," (or "Dear [Company] Engineering Team," if company name is known).
- Length: 200 to 280 words in 3 crisp paragraphs.
- Tone: Confident, technical, and job-search focused.
- Paragraph 1 (The Hook): State directly that you are applying for the [Job Title] role at [Company]. Mention your core specialty (e.g. 4+ years architecting scalable AWS and Kubernetes platforms) and connect it directly to their engineering goals.
- Paragraph 2 (Evidence & Proof): Highlight 2 concrete technical achievements from your resume matching their JD (e.g., cutting deployment times to <1 hour, automating IaC with Terraform, or managing high-availability clusters) with measurable impact.
- Paragraph 3 (Engineering Mindset & Value): Explain your approach to reliability, automation, and cross-functional delivery.
- Closing: A direct call-to-action: "I welcome the opportunity to discuss how my hands-on cloud experience can support [Company]'s platform reliability this quarter."
- Sign off with:
Sincerely,
[Candidate's Real Name]
[Email] | [Phone] | [LinkedIn] (use actual details from resume)

FORBIDDEN CLICHÉS:
- Never say: "I hope this finds you well", "I am writing to express my interest", "passionate about synergy", "collaborative mindset that fosters team innovation", or "culture of excellence".
- Write naturally, like an experienced engineer communicating with an engineering leader."""

    user_prompt = f"""--- CANDIDATE RESUME ---
{req.resume_text}

--- TARGET JOB DESCRIPTION ---
{req.job_description}"""

    content = await call_llm(system_prompt, user_prompt, json_mode=False, api_key=req.api_key)
    return {"cover_letter": content.strip()}


@app.post("/api/download-cover-letter-docx")
async def download_cover_letter_docx(req: DownloadCoverLetterRequest):
    """Generate and return a clean, professionally formatted Microsoft Word (.docx) document."""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Cover letter content cannot be empty.")

    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(11)
    font.color.rgb = RGBColor(30, 41, 59)

    paragraphs = req.content.strip().split("\n\n")
    for para in paragraphs:
        text = para.strip()
        if not text:
            continue
        p = doc.add_paragraph(text)
        p.paragraph_format.line_spacing = 1.18
        p.paragraph_format.space_after = Pt(10)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    filename = (req.filename or "Cover_Letter").removesuffix(".docx") + ".docx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/download-cover-letter-pdf")
async def download_cover_letter_pdf(req: DownloadCoverLetterRequest):
    """Generate and return a clean, professionally formatted PDF document."""
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Cover letter content cannot be empty.")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_margins(22, 22, 22)
    pdf.set_font("Helvetica", size=10.5)
    pdf.set_text_color(30, 41, 59)

    paragraphs = req.content.strip().split("\n\n")
    for para in paragraphs:
        text = para.strip()
        if not text:
            continue
        # Clean unicode characters for standard Helvetica encoding
        clean_text = (
            text.replace("—", "-")
                .replace("–", "-")
                .replace("“", '"')
                .replace("”", '"')
                .replace("’", "'")
                .replace("‘", "'")
                .replace("•", "*")
        )
        pdf.multi_cell(0, 6.5, clean_text)
        pdf.ln(3.5)

    buf = io.BytesIO(pdf.output())
    buf.seek(0)
    filename = (req.filename or "Cover_Letter").removesuffix(".pdf") + ".pdf"
    return Response(
        content=buf.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/generate-outreach")
async def generate_outreach(req: AnalysisRequest):
    """Generate a punchy LinkedIn / cold email outreach message."""
    if not req.resume_text.strip() or not req.job_description.strip():
        raise HTTPException(status_code=400, detail="Both Resume and Job Description are required.")

    system_prompt = """You are an elite tech recruitment and career strategist.
The candidate is actively applying for an OPEN JOB POSITION described in the Job Description.

Generate THREE distinct, practical, job-seeking outreach messages:

### 1. LinkedIn Connection Request Note (STRICTLY UNDER 300 CHARACTERS)
- Must be brief and under 300 characters total.
- State clearly that you noticed the open [Job Title] role at [Company].
- Mention your top matching metric or experience from the resume.
- Call to action: "Open to connecting and sharing my resume?"

### 2. Direct Outreach to the Hiring Manager / Engineering Lead (80-110 words)
- Subject: Application: [Job Title] - [Candidate Name]
- First sentence: Cut straight to the point: "I noticed your team at [Company] is hiring a [Job Title] and wanted to introduce myself directly."
- Value pitch: 2-3 specific sentences connecting your hands-on achievements directly to the tech stack (e.g., AWS, Kubernetes, Terraform, migrations, CI/CD).
- Call to action: "Are you open to a brief 10-minute chat this week to discuss how my background fits your team's immediate infrastructure priorities?"

### 3. Direct Message to the Recruiter / Talent Acquisition (60-80 words)
- Subject: Application Follow-up: [Job Title] - [Candidate Name]
- First sentence: "I recently submitted my application for the [Job Title] position at [Company] and wanted to reach out directly."
- Quick proof of fit: One sentence summarizing years of relevant experience and key matching tools.
- Call to action: "Could you let me know if my background matches what you're looking for an initial recruiter screening call? Happy to send my resume directly."

STRICT RULES:
- FORBIDDEN: Do NOT write "I hope this message finds you well", "I am passionate/excited about", "discuss potential synergy", or "collaboration opportunities". These sound like sales pitches or spam.
- Explicitly state you are applying for the specific open job position.
- Fill in the candidate's actual name, company name, and job title from the inputs."""

    user_prompt = f"""--- CANDIDATE RESUME ---
{req.resume_text}

--- TARGET JOB DESCRIPTION ---
{req.job_description}"""

    content = await call_llm(system_prompt, user_prompt, json_mode=False, api_key=req.api_key)
    return {"outreach_message": content.strip()}


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    with open(os.path.join(os.path.dirname(__file__), "index.html"), "r", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5050))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
