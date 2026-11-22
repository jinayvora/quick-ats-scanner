# Quick ATS Matcher & Career Toolkit

A fast, lightweight, standalone tool that extracts the core functionality from the Resume Matcher suite without any complicated database or multi-step wizard setup.

## Features

- **🎯 Instant ATS Score Match**: Paste or upload your resume (PDF supported) and paste the job description to get an immediate 0-100% score, sub-scores, matched keywords, missing keywords, and recommendations.
- **📝 Targeted Cover Letter**: Generates a tailored, professional 3-paragraph cover letter anchored directly to the JD requirements and your background.
- **💬 Recruiter Outreach**: Generates a punchy LinkedIn connection note (<300 chars) and a direct email/InMail outreach message.

## Quick Start

### Running the App

Double-click `run.bat` or run:

```powershell
cd "H:\Jinay\Claude Projects\Quick-ATS-Tool"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 5050
```

Open your browser at: **http://localhost:5050**
