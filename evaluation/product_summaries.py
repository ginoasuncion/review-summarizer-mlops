import os
from collections import defaultdict

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
os.environ["MLFLOW_TRACKING_URI"] = "http://127.0.0.1:5001"

# Init OpenAI client
client = OpenAI(api_key=api_key)

# Input and output CSV paths
input_csv = os.path.join(os.path.dirname(__file__), "test_product_dataset.csv")
output_csv = os.path.join(os.path.dirname(__file__), "summarized_products.csv")

# Load initial dataset
df = pd.read_csv(input_csv)

# Prompt (choose one or define all three as a dictionary if needed)
PROMPT_TEMPLATE = """
You are a helpful, enthusiastic product reviewer assistant.

Summarize the following transcript of a review for the shoe model: **{product}**.
Your goal is to create a clear, engaging, and friendly summary that feels like
 a recommendation from a trusted friend.

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
        return ""


# Dictionary to store summaries grouped by product
product_summaries = defaultdict(list)

# Generate summaries
for _, row in df.iterrows():
    product = row["product"]
    review_text = row["full_text"]
    summary = summarize_review(product, review_text)
    if summary:
        product_summaries[product].append(summary)

# Create DataFrame from aggregated summaries
output_data = {"product": [], "summaries": []}

for product, summaries in product_summaries.items():
    combined_summary = "\n\n".join(summaries)
    output_data["product"].append(product)
    output_data["summaries"].append(combined_summary)

output_df = pd.DataFrame(output_data)

# Save to CSV
output_df.to_csv(output_csv, index=False, encoding="utf-8")
print(f"✅ Summarized CSV saved to: {output_csv}")
