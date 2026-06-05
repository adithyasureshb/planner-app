from google import genai
import os
from dotenv import load_dotenv
import json
import re
import time
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# =========================
# SAFE JSON PARSER
# =========================
def safe_json_parse(text: str):
    text = text.strip()
    text = re.sub(r"```json|```", "", text).strip()

    match = re.search(r"\[.*\]", text, re.S)
    if match:
        text = match.group()

    return json.loads(text)


# =========================
# STABLE AI GENERATOR (FIXED)
# =========================
def generate_study_plan(subject: str):

    prompt = f"""
Return ONLY JSON.

Task:
Break "{subject}" into simple study topics.

Rules:
- only JSON list of lists
- no explanation

Format:
[
  ["topic1", "topic2"],
  ["topic3"]
]
"""

    models = [
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]

    for model in models:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                return safe_json_parse(response.text)

            except (ResourceExhausted, ServiceUnavailable):
                time.sleep(2 * (attempt + 1))

            except Exception:
                break

    # 🔥 fallback (NEVER FAIL APP)
    return [["Basics"], ["Practice"], ["Revision"]]