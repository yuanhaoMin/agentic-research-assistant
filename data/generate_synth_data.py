import json
import os
from typing import Literal
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, HttpUrl

load_dotenv()


class Company(BaseModel):
    name: str
    industry: str
    headquarters: str
    website: str
    products: list[str]
    partnerships: list[str]
    risk_category: Literal["low", "medium", "high"]
    sensitive_projects: list[str]


class CompaniesFile(BaseModel):
    companies: list[Company] = Field(min_length=10, max_length=10)


class InternalDoc(BaseModel):
    id: str
    title: str
    company: str
    language_hint: Literal["en"]
    text: str


class InternalDocsFile(BaseModel):
    documents: list[InternalDoc] = Field(min_length=10, max_length=10)


client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

companies_prompt = """
Generate exactly 10 synthetic company records as JSON that matches the provided schema.

Style constraints:
- Realistic corporate tone.
- Mix well-known real companies and plausible fictional ones.
- "headquarters" must be a single string like "City, ST" or "City, Country".
- "website" must be a valid https URL string.
- "products" is a list of 2-4 short noun phrases.
- "partnerships" is a list of 0-2 partner names (strings).
- "risk_category" must be one of: low, medium, high.
- "sensitive_projects" is a list of 0-2 internal codenames. Use an empty list if none.
- Keep fields concise and consistent.

Output only JSON that conforms to the schema.
""".strip()

companies_resp = client.responses.parse(
    model="gpt-4o",
    input=[
        {
            "role": "system",
            "content": "You generate structured synthetic datasets that strictly follow a schema.",
        },
        {"role": "user", "content": companies_prompt},
    ],
    text_format=CompaniesFile,
)

companies_obj = companies_resp.output_parsed
companies_list = [c.model_dump() for c in companies_obj.companies]

with open("synth_companies.json", "w", encoding="utf-8") as f:
    json.dump(companies_list, f, ensure_ascii=False, indent=2)

docs_prompt = f"""
You will be given a list of companies as JSON. Create exactly 10 internal document records, one per company, matching the schema.

Hard constraints:
- "company" must match the company "name" EXACTLY.
- "id" must be unique, lowercase snake_case, and include a company hint (e.g., "acme_q2_internal").
- "title" must end with ".pdf" and look like an internal file name (e.g., "Acme_Internal_Strategy.pdf").
- "language_hint" must be "en".
- "text" must be a single paragraph string in an internal memo style.
- If the company's "risk_category" is "medium" or "high", the text MUST include a confidentiality warning sentence (e.g., "Do not disclose ...", "Confidential ... must be redacted externally.").
- If the company has any "sensitive_projects", reference at least one by name in the text and include a non-disclosure instruction.
- If the company has no "sensitive_projects" and is "low" risk, avoid referencing restricted initiatives.

Companies JSON:
{json.dumps(companies_list, ensure_ascii=False, indent=2)}

Output only JSON that conforms to the schema.
""".strip()

docs_resp = client.responses.parse(
    model="gpt-4o",
    input=[
        {
            "role": "system",
            "content": "You generate structured internal-style documents that strictly follow a schema.",
        },
        {"role": "user", "content": docs_prompt},
    ],
    text_format=InternalDocsFile,
)

docs_obj = docs_resp.output_parsed
docs_list = [d.model_dump() for d in docs_obj.documents]

with open("internal_docs.json", "w", encoding="utf-8") as f:
    json.dump(docs_list, f, ensure_ascii=False, indent=2)
