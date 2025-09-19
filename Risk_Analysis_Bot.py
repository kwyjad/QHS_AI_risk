# -*- coding: utf-8 -*-
"""
Main script for the QHS AI Risk Analysis Bot.
This script reads a list of countries, generates a risk analysis for each using
the Gemini API, and then compiles a final report with a summary table.
"""

import os
import time
import logging
import google.generativeai as genai
import backoff
from datetime import datetime
# CORRECTED IMPORT: This now matches your filename "LLM_Prompts.py"
from LLM_Prompts import COUNTRY_ANALYSIS_PROMPT, TABLE_GENERATION_PROMPT

# --- Configuration ---
# Set up basic logging to see progress in the GitHub Actions console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load the Gemini API key from GitHub Secrets
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY secret not found. Please add it to your repository's secrets.")

genai.configure(api_key=GEMINI_API_KEY)

# Configuration for the Gemini models
# Use a safety setting to be less restrictive, as the content is professional analysis
generation_config = {
  "temperature": 0.2,
  "top_p": 1,
  "top_k": 1,
  "max_output_tokens": 8192,
}
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

# Initialize the generative models
# We use Gemini 1.5 Flash as it's fast, has a large context window, and is cost-effective
country_model = genai.GenerativeModel(model_name="gemini-2.5-pro",
                                      generation_config=generation_config,
                                      safety_settings=safety_settings)

table_model = genai.GenerativeModel(model_name="gemini-2.5-pro",
                                    generation_config=generation_config,
                                    safety_settings=safety_settings)

# --- Core Functions ---

@backoff.on_exception(backoff.expo, Exception, max_tries=5, factor=5)
def generate_country_report(country: str) -> str:
    """
    Generates the risk analysis report for a single country.
    Uses exponential backoff to automatically retry on API errors.
    """
    logging.info(f"Generating report for: {country}...")
    try:
        prompt = COUNTRY_ANALYSIS_PROMPT.format(country=country)
        response = country_model.generate_content(prompt)
        # Clean up the response to ensure it's just the markdown block
        report_text = response.text.strip()
        if report_text.startswith("```markdown"):
            report_text = report_text[10:]
        if report_text.endswith("```"):
            report_text = report_text[:-3]
        return report_text.strip()
    except Exception as e:
        logging.error(f"An error occurred while generating report for {country}: {e}")
        # Return an error message to be included in the final report
        return f"# **{country}: Six-Month Risk Outlook**\n\n## ERROR\n\nAn error occurred while generating the report for this country. Please review the logs."

@backoff.on_exception(backoff.expo, Exception, max_tries=3, factor=5)
def generate_summary_table(all_reports_text: str) -> str:
    """
    Generates the final summary table from all the individual reports.
    """
    logging.info("Generating final summary table...")
    try:
        prompt = TABLE_GENERATION_PROMPT.format(all_reports=all_reports_text)
        response = table_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"An error occurred while generating the summary table: {e}")
        return "## Summary Table Generation Failed\n\nAn error occurred. Please review the logs."

def read_countries(file_path: str) -> list:
    """Reads countries from a text file, ignoring empty lines and comments."""
    logging.info(f"Reading country list from {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        countries = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    logging.info(f"Found {len(countries)} countries to process.")
    return countries

# --- Main Execution Logic ---
if __name__ == "__main__":
    logging.info("Starting QHS AI Risk Analysis Bot...")
    
    # CORRECTED FILENAME: This now matches your filename "List_of_Countries.txt"
    countries_file = "List_of_Countries.txt"
    output_file = "Risk_Report.md"
    
    countries = read_countries(countries_file)
    all_reports = []
    
    for i, country in enumerate(countries):
        report = generate_country_report(country)
        all_reports.append(report)
        logging.info(f"Completed {country} ({i+1}/{len(countries)})")
        # Be a good citizen and wait a second between calls to avoid rate limiting
        time.sleep(1)
        
    logging.info("All country reports have been generated.")
    
    # Combine all individual reports into a single text block
    combined_reports_text = "\n\n---\n\n".join(all_reports)
    
    # Generate the summary table
    summary_table = generate_summary_table(combined_reports_text)
    
    # Assemble the final document
    final_report_content = (
        f"# Global Risk Analysis Report\n\n"
        f"**Generated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        f"## Summary Table\n\n{summary_table}\n\n"
        f"---\n\n"
        f"# Individual Country Reports\n\n{combined_reports_text}"
    )
    
    # Write the final report to a file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_report_content)
        
    logging.info(f"Final report successfully generated and saved to {output_file}")
    logging.info("Bot run complete.")
