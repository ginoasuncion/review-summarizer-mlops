import os

import pandas as pd
from dotenv import load_dotenv
from langchain.schema import HumanMessage
from langchain_openai import ChatOpenAI

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(
    temperature=0.7,
    model="gpt-4o",
    openai_api_key=openai_api_key,
    max_tokens=200,
)

# Load your CSV
df = pd.read_csv(
    "C:/Users/kerel/review-summarizer-mlops/lanchain_summarize/video_data.csv"
)


def summarize_shoe_review(model_name):
    try:
        transcript = ""
        for i in range(len(df)):
            transcript += df.iloc[i]["full_text"] + "\n"

        summarize_prompt = (
            "You are a helpful, honest, and knowledgeable chatbot assistant that "
            "answers customer questions about shoes, using insights from a "
            "concatenated transcript of multiple YouTube video reviews.\n\n"
            "Your job is to extract and summarize key reviewer opinions from this "
            "combined transcript to answer the customer’s question. Focus on what "
            "reviewers actually said about the shoe’s comfort, fit, durability, "
            "performance, and style. Use a friendly, trustworthy tone — like you're "
            "helping a friend.\n\n"
            f"Customer Question:\n{model_name}\n\n"
            "Shoe Model:\n[Insert shoe name and version]\n\n"
            "YouTube Review Transcript (combined text):\n"
            f"{transcript}\n\n"
            "Instructions:\n"
            "- Base your answer only on the transcript provided.\n"
            "- If a reviewer is clearly named in the transcript, you may attribute "
            "opinions to them (e.g., “SneakerTalk mentioned…”).\n"
            "- If names are not included, summarize the opinions neutrally "
            "(e.g., “One reviewer said…”).\n"
            "- Do not make up any information not present in the transcript.\n"
            "- Be honest if the transcript doesn't contain enough information to "
            "answer the question.\n"
            "- Keep answers clear, friendly, and reviewer-focused."
        )

        response = llm([HumanMessage(content=summarize_prompt)])
        return response.content.strip()

    except Exception as e:
        return f"Error: {str(e)}"
