# import os
# import pandas as pd
# from langchain_openai import OpenAI  # Updated import
# from dotenv import load_dotenv

# load_dotenv()

# # Load OpenAI API key
# openai_api_key = os.getenv("OPENAI_API_KEY")
# llm = OpenAI(temperature=0, model="gpt-3.5-turbo-instruct",
#  openai_api_key=openai_api_key)

# # Load fake data from CSV
# df = pd.read_csv('C:/Users/kerel/review-summarizer-mlops/
# lanchain_summarize/fake_video_data.csv')
#   # Should work since file is in the same directory

# def summarize_shoe_review(model_name):
#     try:
#         # Find the row where the title contains the model name
#  (case-insensitive)
#         matching_row = df[df['title'].str.contains(model_name, case=False, na=False)]
#         if matching_row.empty:
#             return "No summary available. No video found for this model."

#         # Get the first matching transcript
#         transcript = matching_row.iloc[0]['transcript']

#         # Summarize the transcript using LLM
#         summarize_prompt = f"""
#         Summarize the following YouTube video transcript about '{model_name}'
#         in a concise paragraph (100-150 words):\n\n{transcript}
#         """
#         summary_response = llm(summarize_prompt, max_tokens=200, temperature=0.7)
#         return summary_response.strip()
#     except Exception as e:
#         return f"Error: {str(e)}"
