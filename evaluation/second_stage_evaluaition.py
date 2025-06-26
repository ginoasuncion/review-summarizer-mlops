import os
import mlflow
import pandas as pd
from dotenv import load_dotenv
from mlflow.metrics.genai import make_genai_metric
from openai import OpenAI

# Load environment variables
load_dotenv()
client = OpenAI()
os.environ["MLFLOW_TRACKING_URI"] = "http://127.0.0.1:5001"
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables. Check your .env file.")

# Load and validate data
csv_path = os.path.join(os.path.dirname(__file__), "summarized_products.csv")
if not os.path.exists(csv_path):
    raise FileNotFoundError(f"CSV file not found at {csv_path}")
try:
    df = pd.read_csv(csv_path).sample(n=30, random_state=42)  # Sample 30 rows
    if df.empty or "product" not in df.columns or "summaries" not in df.columns:
        raise ValueError("CSV must contain 'product' and 'summaries' columns with data.")
except Exception as e:
    raise ValueError(f"Error loading CSV: {str(e)}")

# New prompt templates for summarizing concatenated summaries
PROMPTS = [
    (
        "concise_overview",
        """
    You are a professional product review aggregator.

    Provide a concise and engaging overview of the concatenated summaries for the shoe model: **{product}**.
    Your summary should distill the key points from multiple reviews into a single, friendly recommendation.

    Focus on:
    - Overall sentiment (positive, mixed, negative)
    - Common themes in comfort, fit, durability, performance, and style
    - Any notable pros or cons mentioned across reviews

    Keep it brief (1-2 sentences) and avoid repeating verbatim text.

    Concatenated Summaries:
    {text}
    """,
    ),
    (
        "detailed_analysis",
        """
    You are an expert shoe review analyst.

    Create a detailed analysis of the concatenated summaries for the shoe model: **{product}**.
    Break down the key findings into 3-5 bullet points, covering:
    - Consensus on comfort, fit, durability, performance, and style
    - Significant positive or negative feedback
    - Any recurring issues or standout praises

    Use objective language and avoid direct quotes from the summaries.

    Concatenated Summaries:
    {text}
    """,
    ),
    (
        "technical_evaluation",
        """
    You are a technical product evaluation specialist.

    Provide a neutral, technical evaluation of the concatenated summaries for the shoe model: **{product}**.
    Focus on:
    - Material and construction feedback (e.g., quality, wear patterns)
    - Fit and ergonomic observations (e.g., sizing consistency, support)
    - Performance trends (e.g., suitability for specific activities)
    - Design and durability insights

    Keep the tone professional and concise, avoiding personal opinions.

    Concatenated Summaries:
    {text}
    """,
    ),
]

# Define custom evaluation metrics
helpfulness = make_genai_metric(
    name="helpfulness",
    definition="How useful is the summary for understanding key pros and cons?",
    grading_prompt="Rate helpfulness from 1 (not useful) to 5 (extremely useful).",
    version="v1",
    model="openai:/gpt-4",
    parameters={"temperature": 0.0},
    aggregations=["mean"],
    greater_is_better=True,
)

relevance = make_genai_metric(
    name="relevance",
    definition="Does the summary reflect key points from the transcript?",
    grading_prompt="Rate relevance from 1 (unrelated) to 5 (fully relevant).",
    version="v1",
    model="openai:/gpt-4",
    parameters={"temperature": 0.0},
    aggregations=["mean"],
    greater_is_better=True,
)

conciseness = make_genai_metric(
    name="conciseness",
    definition="Is the summary brief and efficient (1-2 sentences)?",
    grading_prompt="Rate conciseness from 1 (wordy) to 5 (very concise).",
    version="v1",
    model="openai:/gpt-4",
    parameters={"temperature": 0.0},
    aggregations=["mean"],
    greater_is_better=True,
)

metrics = [helpfulness, relevance, conciseness]

# Summary function
def summarize(review_text, product, prompt_template, model_name):
    try:
        truncated_text = review_text[:48000]  # Limit input length
        prompt = prompt_template.format(product=product, text=truncated_text)
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error in summarize for {model_name}, {product}: {str(e)}")
        return ""

# Run MLflow experiments
mlflow.set_experiment("summarize-concatenated-eval")

for model_name in ["gpt-3.5-turbo", "gpt-4o"]:
    for prompt_name, prompt_template in PROMPTS:
        run_name = f"{model_name} - {prompt_name}"
        print(f"\nRunning {run_name}...")
        summaries = []

        for _, row in df.iterrows():
            text = row["summaries"]  # Use concatenated summaries
            product = row["product"]
            summary = summarize(text, product, prompt_template, model_name)
            summaries.append(summary)

        eval_df = pd.DataFrame(
            {
                "review": df["summaries"].astype(str).str.slice(0, 12000),  # Use concatenated summaries as review
                "summary": pd.Series(summaries).astype(str).str.slice(0, 3000),
            }
        )

        with mlflow.start_run(run_name=run_name):
            mlflow.log_param("model", model_name)
            mlflow.log_param("prompt_name", prompt_name)

            try:
                results = mlflow.evaluate(
                    data=eval_df,
                    model_type="text-summarization",
                    predictions="summary",
                    targets="review",
                    extra_metrics=metrics,
                    evaluator_config={
                        "col_mapping": {"inputs": "review", "outputs": "summary"},
                    },
                )
                print("Scores:", results.metrics)
            except Exception as e:
                print(f"Error in evaluation for {run_name}: {str(e)}")

print("All experiments completed!")