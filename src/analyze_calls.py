import os
import json
from groq import Groq

INPUT_DIR = "converted_transcripts"
OUTPUT_DIR = "analysis_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

client = Groq()

SYSTEM_PROMPT = """
You are an expert QA system for debt-collection call analysis.
Return STRICT JSON matching the schema below. Do not include markdown or extra text.

Schema:
{
  "payment_attempted": boolean,
  "customer_intent": boolean,
  "customer_sentiment": {
    "classification": "Satisfied|Neutral|Frustrated|Hostile",
    "description": string
  },
  "agent_performance": string,
  "timestamped_events": [
    {"timestamp": "m:ss", "event_type": "disclosure|offer_negotiation|payment_setup_attempt|frustration_hostility", "description": string}
  ]
}
"""

def process_transcript(transcript):
    messages = [
        {"role": "user", "content": SYSTEM_PROMPT + "\n\nTranscript:\n<<<BEGIN_TRANSCRIPT>>>\n" + json.dumps(transcript, indent=2) + "\n<<<END_TRANSCRIPT>>>"},
    ]

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.4,
        max_completion_tokens=1024
    )

    return response.choices[0].message.content

for filename in os.listdir(INPUT_DIR):
    if not filename.endswith(".json"):
        continue
    
    path = os.path.join(INPUT_DIR, filename)
    with open(path, "r") as f:
        transcript_data = json.load(f)

    result = process_transcript(transcript_data)

    # write output
    out_path = os.path.join(OUTPUT_DIR, filename.replace(".json", "_analysis.json"))
    with open(out_path, "w") as f:
        f.write(result)

    print(f"✅ Processed: {filename} → {out_path}")
