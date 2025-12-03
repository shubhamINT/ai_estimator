from openai import OpenAI
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import base64
from structure import EstimationResponse

load_dotenv(override=True)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
gemini_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


# Call OpenAI
async def openai_call(system_prompt, user_prompt,file_list=[], output_structure = EstimationResponse, model="gpt-4.1"):

    # 1. Standard messages
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # 2. Add each file as a separate entry
    if file_list:
        for file_obj in file_list:
            # Encode bytes to base64 string
            b64_string = base64.b64encode(file_obj['data']).decode('utf-8')

            # Assuming your wrapper supports this custom role/format:
            messages.append({
                "role": "user", 
                "content": [
                    {
                        "type": "input_file",
                        "filename": file_obj['name'],
                        "file_data": f"data:application/pdf;base64,{b64_string}"
                    }
                ],
            })

    response = openai_client.responses.parse( # or beta.chat.completions.parse
        model=model,
        input=messages, # Pass the list containing multiple file entries
        text_format=output_structure,
    )

    return response.output_parsed.model_dump()

async def gemini_call(system_prompt, user_prompt, file_list=[], output_structure = EstimationResponse, model="gemini-2.0-flash"):

    # 1. Create the text part
    request_contents = [user_prompt]

    # 2. Append each file as a separate "Part"
    if file_list:
        for file_obj in file_list:
            request_contents.append(
                types.Part.from_bytes(
                    data=file_obj['data'],
                    mime_type='application/pdf' # Or use file_obj['mime']
                )
            )

    response = gemini_client.models.generate_content(
        model=model,   
        contents=request_contents, # Pass the list containing prompt + all PDFs
        config={
            "system_instruction": system_prompt,
            "response_mime_type": "application/json",
            "response_json_schema": output_structure.model_json_schema(),
        },
    )

    return response.parsed