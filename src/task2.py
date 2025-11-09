from groq import Groq
import requests
import json
import re
import os
import os
import json
import json
import re

# Initialize Groq client

client = Groq()

API_URL = "https://se-payment-verification-api.service.external.usea2.aws.prodigaltech.com/api/validate-payment"


url_get = "https://se-payment-verification-api.service.external.usea2.aws.prodigaltech.com/api/payment-ids"

response = requests.get(url_get)
payment_ids = response.json()


SYSTEM_PROMPT = """
You are a precise payment processing assistant. You read call transcripts and extract payment attempts.
If payment credentials are provided, you call the provided tool `validate_payment` to validate the payment.

Follow these instructions exactly:

1) Identify every payment attempt in the transcript. A payment attempt happens only when the customer provides or is asked to provide payment credentials (card or ACH).

2) For each attempt, extract:
   - method: "card" or "ach"
   - card_number: Digits only, exactly as spoken. Do not guess missing digits. Do not pad or complete numbers. Card number must be between 12-16 digits. Partial card numbers are not accepted. Card numbers more than 16 digits are not accepted
   - expiry_month: in mm format (extract only if spoken)
   - expiry_year: in yyyy format (extract only if spoken)
   - cvv: Extract if spoken, else null.
   - cardholder_name: If the transcript states a name.
   - payment_amount: If the transcript states a payment amount. Doesnt matter if its valid or invalid, ALWAYS PUT AMOUNT if its stated in the transcript

3) Determine validity:
   - validity = "valid" if credentials appear complete.
   - validity = "invalid" if any required fields are missing.

4) If invalid, assign one failure_reason, dont invent any other reason:
    - none
    - invalid_card_length (card length should be between 12-16 ONLY)
    - invalid_args
    - expired_card (a valid expiry year is 2025 onwards, expiry year cannot be in past)
    - special_characters
    - invalid_cvv_length (a valid CVV length should be either 3 or 4 ONLY)

5) Output ONLY one or more tool calls:
   validate_payment({
      "id": assign a random number (STRING),
      "student_id": 70322000054(keep this fixed at ALL TIMES) (STRING),
      "payment_valid": (validity == "valid") (BOOLEAN),
      "failure_reason": failure_reason or "none" (STRING),
      "amount": payment_amount (NUMBER),
      "credentials": {
         "cardholderName": cardholder_name (STRING), 
         "cardNumber": card_number (STRING),
         "expiryMonth": expiry_month (NUMBER),
         "expiryYear": expiry_year (NUMBER),
         "cvv": cvv (STRING)
      }
   })

6) Do NOT add extra commentary. Do NOT explain. DO NOT INCLUDE MARKDOWN . GIVE JSON OUTPUT ALWAYS. Keep the last meaningful payment attempt and ignore earlier ones. GIVE ONLY ONE TOOL CALL.
"""




def parse_tool_call(output: str):
    output = output.strip()

    # Case 1: pure JSON object
    if output.startswith("{") and output.endswith("}"):
        return json.loads(output)

    # Case 2: one or more validate_payment({...}) calls - take the LAST one
    matches = re.findall(r"validate_payment\((\{.*?\})\)", output, flags=re.DOTALL)
    if matches:
        json_str = matches[-1]  # keep final attempt only
        json_str = json_str.replace("None", "null").replace("False", "false").replace("True", "true")
        return json.loads(json_str)

    # Case 3: No payment attempt → return None
    return None




def run_llm(transcript_text):
    # Request non-streaming completion so we receive the final text only
    completion = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        stream=False,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": transcript_text}
        ]
    )

    # Extract the returned content. Different client versions may expose
    # the content under choices[0].message.content (standard) or
    # choices[0].text for some implementations—try the common case first.
    try:
        return completion.choices[0].message.content
    except Exception:
        try:
            return completion.choices[0].text
        except Exception:
            # As a last resort, return the str() of the object
            return str(completion)


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
    folder = "converted_transcripts"
    json_files = [f for f in os.listdir(folder) if f.endswith(".json")]
    results = []

    for file in json_files:
        filepath = os.path.join(folder, file)
        filename = file.replace(".json", "")  # id
        with open(filepath, "r") as f:
            transcript = json.load(f)

        transcript_text = "\n".join(x["utterance"] for x in transcript)

        llm_output_text = run_llm(transcript_text)

        raw_output = parse_tool_call(llm_output_text)

        if raw_output is None:
            # No payment attempt detected for this file
            results.append({"id": filename, "result": "no_payment_attempt"})
            continue

        raw_output["id"] = filename
        raw_output["student_id"] = "70322000054"
        raw_output["credentials"]["cardNumber"] = re.sub(r"\D", "", raw_output["credentials"]["cardNumber"] or "")

        # sanitize card number to digits only
        card_number = raw_output["credentials"]["cardNumber"]

        # Validate card length: must be between 12 and 16 digits
        if not card_number or len(card_number) < 12 or len(card_number) > 16:
            # Set failure fields so downstream systems know why we didn't call the API
            raw_output["payment_valid"] = False
            raw_output["failure_reason"] = "invalid_card_length"

            updated_tool_call = f"validate_payment({json.dumps(raw_output)})"

            # Only print the final tool call and the (local) API-like response
            print(updated_tool_call)

            # produce a local result similar to what the external API returns for clarity
            result = {
                "success": False,
                "message": "Payment declined",
                "failureReason": "invalid_card_length",
                "details": f"Card number must be between 12-16 digits. Received {len(card_number)}"
            }

            print(result)
            results.append({"id": filename, "result": result})
            continue

        updated_tool_call = f"validate_payment({json.dumps(raw_output)})"

        # Print only the final tool call and the API response
        print(updated_tool_call)
        result = call_payment_api(updated_tool_call)
        print(result)

        results.append({"id": filename, "result": result})

    print("\n\n========== SUMMARY ==========\n")
    for r in results:
        print(r)
