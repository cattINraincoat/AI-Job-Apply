# app/services/resume_parser.py

import pdfplumber
import io
import re
import httpx
import json
from typing import Dict

OLLAMA_MODEL = "llama3.2:3b"
OLLAMA_API_URL = "http://127.0.0.1:11434/api/generate"

def extract_pdf_text(file_bytes: bytes) -> str:
    """Extract text from PDF using pdfplumber."""
    print("📄 Extracting text from PDF...")
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
            print(f"  Page {i} text length: {len(page_text) if page_text else 0}")
    print(f"Total extracted text length: {len(text)}")
    return text

def extract_basic_info(text: str) -> Dict:
    """Extract basic info like name, email, phone using regex."""
    print("🔍 Extracting basic info using regex...")
    email = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
    phone = re.findall(r"\+?\d[\d -]{8,}\d", text)
    name = text.split("\n")[0] if text else "Unknown"

    info = {
        "name": name.strip(),
        "email": email[0] if email else None,
        "phone": phone[0] if phone else None,
        "raw_text": text
    }
    print(f"Extracted basic info: {info}")
    return info




async def parse_resume_with_llm(file_bytes: bytes) -> Dict:
    """
    Extracts text from PDF, applies basic regex extraction,
    then uses Ollama LLM to parse structured JSON with headings as keys.
    """
    # Step 1: Extract text
    text = extract_pdf_text(file_bytes)

    # Step 2: Basic info
    basic_info = extract_basic_info(text)

    # Step 3: Prepare LLM prompt
    prompt = f"""
    You are a smart resume parser. Convert the following resume text into a JSON object.
    Use headings as keys (like "Education", "Skills", "Experience") and map the content under them as values.
    Also include "name", "email", and "phone" if possible.

    IMPORTANT: Only output one valid JSON object.
    Do NOT include explanations, markdown, or multiple JSONs.

    --- SCHEMA INSTRUCTIONS ---
    1.  **"Experience"**: MUST be an **array of objects**. Each object must represent one Job or Project and contain the keys: "title", "company_or_project", "dates", and "description_bullets" (which is an array of strings).
    2.  **"Education"**: MUST be an **array of objects**. Each object must contain the keys: "degree", "institution", "dates", and "gpa_or_percent".
    3.  **"Skills"**: Should be an **object** where keys are skill categories (e.g., "Languages", "Frameworks") and values are arrays of strings.

    Resume:
    {text}

    JSON output:
    """
    print("🤖 Sending prompt to Ollama...")

    # Step 4: Call Ollama asynchronously (Original httpx call restored)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                OLLAMA_API_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "max_tokens": 1500}
            )
            response.raise_for_status()

            # The response body structure depends on the Ollama API, 
            # typically the generated text is under the 'response' key in the /api/generate endpoint.
            raw_response = response.json().get("response")

        print("✅ Raw response from Ollama:")
        print(raw_response)
        print("TYPE OF raw_response:", type(raw_response))
        print("----- END OF RAW RESPONSE -----")

        # -----------------------------
        # Handle different response types
        # -----------------------------
        if isinstance(raw_response, dict):
            # Already a dict — no parsing needed (less common for text generation)
            structured_data = raw_response
            print("✅ raw_response is dict, using directly")

        elif isinstance(raw_response, str):
            # ... (inside elif isinstance(raw_response, str): block)

            # Clean string: Remove markdown fences (```json ... ``` or ``` ... ```)
            # We keep this step to handle markdown formatting from the LLM
            llm_output_clean = re.sub(r"```(?:json)?\s*([\s\S]*?)\s*```", r"\1", raw_response, flags=re.DOTALL).strip()
            llm_output_clean = llm_output_clean.strip() # Final trim

            print("✅ Cleaned LLM output:")
            print(llm_output_clean)
            print("----- END OF CLEANED OUTPUT -----")

            # **FIX APPLIED HERE:** Use a non-greedy regex to find the FIRST complete JSON object.
            # r'(\{[\s\S]*?\})' -> The '?' makes the match lazy, stopping at the earliest '}'
            json_match = re.search(r'(\{[\s\S]*?\})', llm_output_clean)

            if json_match:
                llm_json_str = json_match.group(1)
                print("✅ JSON string extracted.")

                try:
                    # Attempt to load the extracted JSON string
                    structured_data = json.loads(llm_json_str)
                    print("✅ Successfully parsed JSON from LLM output")
                except json.JSONDecodeError as je:
                    # This catches issues like invalid JSON syntax *within* the braces
                    print(f"⚠️ JSONDecodeError: {je}")
                    structured_data = basic_info
                    print("⚠️ Falling back to basic info")
            else:
                print("⚠️ No valid JSON object found in string, using fallback")
                structured_data = basic_info

            # ... (rest of the function)
        else:
            print("⚠️ Unknown response type, using fallback")
            structured_data = basic_info

        # Merge basic info if LLM missed it
        for k in ["name", "email", "phone"]:
            if k not in structured_data and k in basic_info:
                structured_data[k] = basic_info[k]

    except Exception as e:
        # This catches network errors, timeout errors, or unexpected Ollama response formats
        print(f"⚠️ Error during LLM parsing: {e}")
        structured_data = basic_info
        print("⚠️ Falling back to basic info")

    print("🎯 Final structured data keys:", list(structured_data.keys()))

    return structured_data

# async def parse_resume_with_llm(file_bytes: bytes) -> Dict:
#     """
#     Extracts text from PDF, applies basic regex extraction,
#     then uses Ollama LLM to parse structured JSON with headings as keys.
#     """
#     # Step 1: Extract text
#     text = extract_pdf_text(file_bytes)

#     # Step 2: Basic info
#     basic_info = extract_basic_info(text)

#     # Step 3: Prepare LLM prompt
#     prompt = f"""
# You are a smart resume parser. Convert the following resume text into a JSON object.
# Use headings as keys (like "Education", "Skills", "Experience") and map the content under them as values.
# Also include "name", "email", and "phone" if possible.

# IMPORTANT: Only output one valid JSON object.
# Do NOT include explanations, markdown, or multiple JSONs.


# Resume:
# {text}

# JSON output:
# """
#     print("🤖 Sending prompt to Ollama...")

#     # Step 4: Call Ollama asynchronously
#     # -----------------------------
#     # Step 4: Call Ollama asynchronously
#     # -----------------------------
#     print("🤖 Sending prompt to Ollama...")

# # -----------------------------
# # Step 4: Call Ollama asynchronously
# # -----------------------------
#     print("🤖 Sending prompt to Ollama...")

#     try:
#         async with httpx.AsyncClient(timeout=60) as client:
#             response = await client.post(
#                 OLLAMA_API_URL,
#                 json={"model": OLLAMA_MODEL, "prompt": prompt, "max_tokens": 1500}
#             )
#             response.raise_for_status()

#             raw_response = response.json().get("response")
#             print("✅ Raw response from Ollama:")
#             print(raw_response)
#             print("TYPE OF raw_response:", type(raw_response))
#             print("----- END OF RAW RESPONSE -----")

#             # -----------------------------
#             # Handle different response types
#             # -----------------------------
#             if isinstance(raw_response, dict):
#                 # Already a dict — no parsing needed
#                 structured_data = raw_response
#                 print("✅ raw_response is dict, using directly")

#             elif isinstance(raw_response, str):
#                 # Clean string
#                 llm_output_clean = re.sub(r"```.*?```", "", raw_response, flags=re.DOTALL).strip()
#                 print("✅ Cleaned LLM output:")
#                 print(llm_output_clean)
#                 print("----- END OF CLEANED OUTPUT -----")

#                 # Extract first JSON object from string
#                 start = llm_output_clean.find("{")
#                 end = llm_output_clean.rfind("}") + 1

#                 if start != -1 and end != -1:
#                     llm_json_str = llm_output_clean[start:end]
#                     print("✅ JSON string to parse:")
#                     print(llm_json_str)
#                     try:
#                         structured_data = json.loads(llm_json_str)
#                         print("✅ Successfully parsed JSON from LLM output")
#                     except json.JSONDecodeError as je:
#                         print(f"⚠️ JSONDecodeError: {je}")
#                         structured_data = basic_info
#                         print("⚠️ Falling back to basic info")
#                 else:
#                     print("⚠️ No JSON found in string, using fallback")
#                     structured_data = basic_info
#             else:
#                 print("⚠️ Unknown response type, using fallback")
#                 structured_data = basic_info

#             # Merge basic info if missing
#             for k in ["name", "email", "phone"]:
#                 if k not in structured_data and k in basic_info:
#                     structured_data[k] = basic_info[k]

#     except Exception as e:
#         print(f"⚠️ Error during LLM parsing: {e}")
#         structured_data = basic_info
#         print("⚠️ Falling back to basic info")

#     print("🎯 Final structured data keys:", list(structured_data.keys()))


#     return structured_data


# import pdfplumber
# import io
# import re

# def parse_resume(file_bytes: bytes) -> dict:
#     """
#     Extracts text from PDF and parses basic details into JSON.
#     """
#     text = ""

#     with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
#         for page in pdf.pages:
#             text += page.extract_text() + "\n"

#     # Very basic regex-based info extraction (we’ll improve this later)
#     email = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
#     phone = re.findall(r"\+?\d[\d -]{8,}\d", text)
#     name = text.split("\n")[0] if text else "Unknown"

#     parsed_data = {
#         "name": name.strip(),
#         "email": email[0] if email else None,
#         "phone": phone[0] if phone else None,
#         "raw_text": text
#     }

#     return parsed_data
