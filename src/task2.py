from groq import Groq
import requests
import json
import re

# Initialize Groq client
client = Groq()

API_URL = "https://se-payment-verification-api.service.external.usea2.aws.prodigaltech.com/api/validate-payment"

SYSTEM_PROMPT = """
You are a precise payment processing assistant. You read call transcripts and extract payment attempts.
If payment credentials are provided, you call the provided tool `validate_payment` to validate the payment.

Follow these instructions exactly:

1) Identify every payment attempt in the transcript. A payment attempt happens only when the customer provides or is asked to provide payment credentials (card or ACH).

2) For each attempt, extract:
   - attempt_id: "attempt-1", "attempt-2", ...
   - method: "card" or "ach"
   - card_number: Digits only, exactly as spoken. Do not guess missing digits. Do not pad or complete numbers.
   - expiry_mm and expiry_yy: Extract if spoken. If not spoken, set to null.
   - cvv: Extract if spoken, else null.
   - cardholder_name: If the transcript states a name.
   - amount_cents: Convert the payment amount to cents.

3) Determine validity:
   - validity = "valid" if credentials appear complete.
   - validity = "invalid" if any required fields are missing.

4) If invalid, assign one failure_reason:
   - "invalid_card_number_length"
   - "missing_expiry"
   - "missing_cvv"
   - "expired_card"
   - "masked_or_incomplete"
   - "amount_missing"
   - "name_missing"

5) Output one or more tool calls:
   validate_payment({
      "id": attempt_id,
      "student_id": 70322000054(keep this fixed at ALL TIMES),
      "payment_valid": (validity == "valid"),
      "failure_reason": failure_reason or "none",
      "amount": amount_cents / 100,
      "credentials": {
         "card_number": card_number,
         "expiry": expiry_mm and expiry_yy formatted as "MM/YY" or null,
         "cvv": cvv
      }
   })

6) Do NOT add extra commentary. Do NOT explain.
"""


def run_llm(transcript_text):
    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        stream=True,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript_text}
        ]
    )

    result_chunks = []
    for chunk in completion:
        text = chunk.choices[0].delta.content
        if text:
            print(text, end="")   # show streaming output
            result_chunks.append(text)

    print()  # spacing
    return "".join(result_chunks)


def call_payment_api(output_text):
    match = re.search(r"validate_payment\((\{.*?\})\)", output_text, re.DOTALL)
    if not match:
        raise ValueError("No validate_payment(...) call found in model output.\nOUTPUT:\n" + output_text)

    json_str = match.group(1)

    # Convert Python -> JSON
    json_str = json_str.replace("None", "null")
    json_str = json_str.replace("False", "false")
    json_str = json_str.replace("True", "true")

    args = json.loads(json_str)

    response = requests.post(API_URL, json=args)
    try:
        return response.json()
    except:
        return {"error": response.text, "status": response.status_code}



if __name__ == "__main__":
    # Load sample transcript file (replace with your path)
    with open("converted_transcripts/a4c8d2e7.json", "r") as f:
        transcript = json.load(f)

    # Convert transcript JSON → text list (just flatten utterances)
    transcript_text = "\n".join(x["utterance"] for x in transcript)

    print("\n--- RUNNING MODEL ---\n")
    raw_output = run_llm(transcript_text)

    print("\n--- CALLING PAYMENT API ---\n")
    result = call_payment_api(raw_output)
    print(result)
