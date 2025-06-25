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
    raise ValueError(
        "OPENAI_API_KEY not found in environment variables. Check your .env file."
    )

# Load and sample data
csv_path = os.path.join(os.path.dirname(__file__), "test_product_dataset.csv")
df = pd.read_csv(csv_path).sample(n=50, random_state=42)

# Prompt templates
PROMPTS = [
    (
        "friendly_summary",
        """
        You are a helpful, enthusiastic product reviewer assistant.

        Summarize the following transcript of
          a review for the shoe model: **{product}**.
        Your goal is to create a clear, engaging, and friendly summary that feels
        like a recommendation from a trusted friend.

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
        """,
    ),
    (
        "bullet_points",
        """
        You are a shoe review summarizer. Read the transcript for the shoe model:
        **{product}** and extract key insights.

        Write **3–5 informative bullet points** that summarize the review,
        focusing on **objective observations and reviewer opinions**.

        Each bullet should:
        - Start with a strong, clear statement
        - Emphasize **comfort**, **fit**, **durability**, **performance**, or **style**
        - Mention standout phrases or concerns (e.g., "glue stains", "true to size")

        Be concise but complete.

        Transcript:
        {text}
        """,
    ),
    (
        "technical_summary",
        """
        You are a professional product analyst.

        Write a concise, technical summary of the review transcript for the
        shoe model: **{product}** aimed at product designers or sneaker reviewers.

        Focus on:
        - **Materials** used (e.g., suede, mesh, leather)
        - **Construction quality** (e.g., stitching, glue stains, sole type)
        - **Fit and ergonomics** (e.g., arch support, flexibility, toe box shape)
        - **Performance** feedback (e.g., suitable for running, walking, lifestyle)
        - **Design details** (e.g., aesthetics, branding, iconic elements)

        Avoid personal tone. Keep the summary neutral and focused on design value.

        Transcript:
        {text}
        """,
    ),
]

# Define evaluation metrics
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
    truncated_text = review_text[:48000]
    prompt = prompt_template.format(product=product, text=truncated_text)
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


# Run MLflow experiments
mlflow.set_experiment("summarize-product-eval-single-video")

for model_name in ["gpt-3.5-turbo", "gpt-4o"]:
    for prompt_name, prompt_template in PROMPTS:
        run_name = f"{model_name} - {prompt_name}"
        print(f"\nRunning {run_name}...")
        summaries = []

        for _, row in df.iterrows():
            text = row["full_text"]
            product = row["product"]
            summary = summarize(text, product, prompt_template, model_name)
            summaries.append(summary)

        eval_df = pd.DataFrame(
            {
                "review": df["full_text"].str.slice(0, 12000),
                "summary": pd.Series(summaries).str.slice(0, 3000),
            }
        )

        with mlflow.start_run(run_name=run_name):
            mlflow.log_param("model", model_name)
            mlflow.log_param("prompt_name", prompt_name)

            results = mlflow.evaluate(
                data=eval_df,
                model_type="text-summarization",
                evaluators="default",
                extra_metrics=metrics,
                predictions="summary",
                targets="review",
                evaluator_config={
                    "col_mapping": {"inputs": "review", "outputs": "summary"}
                },
            )

            print("Scores:", results.metrics)

# Done!
