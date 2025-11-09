import streamlit as st
import json
import pandas as pd
from task2 import run_llm, parse_tool_call, call_payment_api
import os

st.set_page_config(page_title="Call Analysis Dashboard", page_icon="📞", layout="wide")

def analyze_transcript(transcript_text, filename=None):
    # Task 2: Payment Analysis
    llm_output_text = run_llm(transcript_text)
    payment_analysis = parse_tool_call(llm_output_text)
    
    if payment_analysis:
        payment_analysis["student_id"] = "70322000054"
        # Set the ID as filename if provided, otherwise generate a random one
        if filename:
            payment_analysis["id"] = filename.replace(".json", "")
        # Validate card number format
        if "credentials" in payment_analysis and payment_analysis["credentials"].get("cardNumber"):
            card_number = ''.join(filter(str.isdigit, payment_analysis["credentials"]["cardNumber"]))
            payment_analysis["credentials"]["cardNumber"] = card_number
            
        # Call payment validation API
        api_call = f"validate_payment({json.dumps(payment_analysis)})"
        try:
            api_response = call_payment_api(api_call)
        except Exception as e:
            api_response = {"error": str(e), "success": False}
    else:
        api_response = {"message": "No payment attempt detected", "success": False}
    
    return payment_analysis, api_response

def format_payment_details(payment_data):
    if not payment_data:
        return "No payment attempt detected"
    
    details = []
    if "credentials" in payment_data:
        creds = payment_data["credentials"]
        if creds.get("cardNumber"):
            details.append(f"Card Number: {'*' * (len(creds['cardNumber'])-4) + creds['cardNumber'][-4:]}")
        if creds.get("expiryMonth") and creds.get("expiryYear"):
            details.append(f"Expiry: {creds['expiryMonth']}/{creds['expiryYear']}")
        if creds.get("cardholderName"):
            details.append(f"Cardholder: {creds['cardholderName']}")
    
    if payment_data.get("amount"):
        details.append(f"Amount: ${payment_data['amount']}")
    
    if payment_data.get("payment_valid") is not None:
        status = "Valid" if payment_data["payment_valid"] else "Invalid"
        details.append(f"Status: {status}")
        
    if payment_data.get("failure_reason") and payment_data["failure_reason"] != "none":
        details.append(f"Failure Reason: {payment_data['failure_reason']}")
    
    return "\n".join(details)

# Sidebar
st.sidebar.title("Upload Options")
upload_option = st.sidebar.radio(
    "Choose input method:",
    ["Upload JSON File", "Paste Transcript"]
)

# Main content
st.title("Call Analysis Dashboard")

if upload_option == "Upload JSON File":
    uploaded_file = st.file_uploader("Upload a JSON transcript file", type="json")
    if uploaded_file:
        try:
            transcript_data = json.load(uploaded_file)
            if isinstance(transcript_data, list):
                transcript_text = "\n".join(x.get("utterance", "") for x in transcript_data)
            else:
                transcript_text = transcript_data.get("transcript", "")
            
            st.subheader("Transcript")
            with st.expander("Show Transcript"):
                st.text(transcript_text)
                
            filename = uploaded_file.name
            payment_analysis, api_response = analyze_transcript(transcript_text, filename)
            
            # Display Results
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Payment Analysis")
                st.text_area("Payment Details", format_payment_details(payment_analysis), height=200)
            
            with col2:
                st.subheader("API Request & Response")
                
                # Show tool call
                st.markdown("**Tool Call Body:**")
                st.code(json.dumps(payment_analysis, indent=2), language="json")
                
                # Show API Response
                st.markdown("**API Response:**")
                success = api_response.get("success", False)
                color = "green" if success else "red"
                st.markdown(f'<div style="padding: 10px; border-radius: 5px; background-color: {color}; color: white;">'
                          f'{json.dumps(api_response, indent=2)}</div>', unsafe_allow_html=True)
                
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")

else:  # Paste Transcript
    transcript_text = st.text_area("Paste your transcript here:", height=200)
    custom_filename = st.text_input("Enter an ID for this transcript (optional):")
    if st.button("Analyze") and transcript_text:
        filename = f"{custom_filename}.json" if custom_filename else None
        payment_analysis, api_response = analyze_transcript(transcript_text, filename)
        
        # Display Results
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Payment Analysis")
            st.text_area("Payment Details", format_payment_details(payment_analysis), height=200)
        
        with col2:
            st.subheader("API Request & Response")
            
            # Show tool call
            st.markdown("**Tool Call Body:**")
            st.code(json.dumps(payment_analysis, indent=2), language="json")
            
            # Show API Response
            st.markdown("**API Response:**")
            success = api_response.get("success", False)
            color = "green" if success else "red"
            st.markdown(f'<div style="padding: 10px; border-radius: 5px; background-color: {color}; color: white;">'
                      f'{json.dumps(api_response, indent=2)}</div>', unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("Call Analysis Tool - Powered by Groq LLM")