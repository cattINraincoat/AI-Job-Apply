from fastapi import APIRouter, UploadFile, File, HTTPException
from services.resume_parser import parse_resume_with_llm

router = APIRouter()

@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    # Allow only PDF for now
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported at this stage.")
    
    contents = await file.read()

    parsed_data = await parse_resume_with_llm(contents)

    return {
        "filename": file.filename,
        "parsed_data": parsed_data
    }
