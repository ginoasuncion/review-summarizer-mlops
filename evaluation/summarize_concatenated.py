import os
from collections import defaultdict

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables. Check your .env file.")
os.environ["MLFLOW_TRACKING_URI"] = "http://127.0.0.1:5001"

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

# Input and output CSV paths
input_csv = os.path.join(os.path.dirname(__file__), "summarized_products.csv")
output_csv = os.path.join(os.path.dirname(__file__), "summary_of_summaries.csv")

# Validate and load initial dataset with sampling
if not os.path.exists(input_csv):
    raise FileNotFoundError(f"Input CSV not found at {input_csv}")
try:
    df = pd.read_csv(input_csv).sample(n=15, random_state=42)  # Sample 20 rows
    if df.empty or "product" not in df.columns or "summaries" not in df.columns:
        raise ValueError("Input CSV must contain 'product' and 'summaries' columns with data.")
except Exception as e:
    raise ValueError(f"Error loading input CSV: {str(e)}")

# Prompt template for summarizing concatenated summaries
PROMPT_TEMPLATE = """
You are a helpful, enthusiastic product review aggregator.

Summarize the following concatenated summaries of reviews for the shoe model: **{product}**.
Your goal is to create a clear, engaging, and concise final summary that distills the key points from multiple reviews into a single recommendation.

Emphasize:
- Overall sentiment (positive, mixed, negative)
- Common themes in comfort, fit, durability, performance, and style
- Key pros and cons mentioned across reviews

Keep the summary brief (1-2 paragraphs) and avoid repeating verbatim text.

Concatenated Summaries:
{text}
"""

# Summarization function
def summarize_concatenated(product, concatenated_summaries, model="gpt-4o"):
    prompt = PROMPT_TEMPLATE.format(product=product, text=concatenated_summaries[:48000])
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error summarizing {product}: {e}")
        return ""  # Return empty string to allow aggregation to continue

# Dictionary to store final summaries
final_summaries = defaultdict(str)

# Generate final summaries
for _, row in df.iterrows():
    product = row["product"]
    concatenated_summaries = row["summaries"]
    final_summary = summarize_concatenated(product, concatenated_summaries)
    if final_summary:  # Only update if summary is non-empty
        final_summaries[product] = final_summary

# Create DataFrame from final summaries
output_data = {"product": [], "final_summary": []}
for product, summary in final_summaries.items():
    output_data["product"].append(product)
    output_data["final_summary"].append(summary)

output_df = pd.DataFrame(output_data)

# Save to CSV with error handling
try:
    output_df.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"✅ Summary of summaries CSV saved to: {output_csv}")
except Exception as e:
    print(f"Error saving output CSV: {e}")
    raise