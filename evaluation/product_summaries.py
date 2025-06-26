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
input_csv = os.path.join(os.path.dirname(__file__), "test_product_dataset.csv")
output_csv = os.path.join(os.path.dirname(__file__), "summarized_products.csv")

# Validate and load initial dataset with sampling
if not os.path.exists(input_csv):
    raise FileNotFoundError(f"Input CSV not found at {input_csv}")
try:
    df = pd.read_csv(input_csv).sample(n=30, random_state=42)  # Sample 30 rows
    if df.empty or "product" not in df.columns or "full_text" not in df.columns:
        raise ValueError("Input CSV must contain 'product' and 'full_text' columns with data.")
except Exception as e:
    raise ValueError(f"Error loading input CSV: {str(e)}")

# Prompt template
PROMPT_TEMPLATE = """
You are a helpful, enthusiastic product reviewer assistant.

Summarize the following transcript of a review for the shoe model: **{product}**.
Your goal is to create a clear, engaging, and friendly summary that feels like a recommendation from a trusted friend.

Emphasize:
- What the reviewer liked or disliked
- Comfort (daily wear, cushioning, sizing)
- Fit (true to size? narrow? wide?)
- Durability (build quality, longevity, visible wear)
- Performance (how it feels while walking/running, use cases)
- Style (appearance, versatility, colorways)

Avoid repeating the transcript. Keep it grounded in what was actually said.

Transcript:
{text}
"""

# Summarization function
def summarize_review(product, review_text, model="gpt-4o"):
    prompt = PROMPT_TEMPLATE.format(product=product, text=review_text[:48000])
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

# Dictionary to store summaries grouped by product
product_summaries = defaultdict(list)

# Generate summaries
for _, row in df.iterrows():
    product = row["product"]
    review_text = row["full_text"]
    summary = summarize_review(product, review_text)
    if summary:  # Only append non-empty summaries
        product_summaries[product].append(summary)

# Create DataFrame from aggregated summaries
output_data = {"product": [], "summaries": []}
for product, summaries in product_summaries.items():
    combined_summary = "\n\n".join(summaries)
    output_data["product"].append(product)
    output_data["summaries"].append(combined_summary)

output_df = pd.DataFrame(output_data)

# Save to CSV with error handling
try:
    output_df.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"✅ Summarized CSV saved to: {output_csv}")
except Exception as e:
    print(f"Error saving output CSV: {e}")
    raise