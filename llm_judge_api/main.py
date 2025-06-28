import os
import json
import logging
import time
from typing import Dict, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import openai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="LLM Judge API", description="API for evaluating summaries using LLM judge")

class EvaluationRequest(BaseModel):
    summary_content: str
    search_query: str
    video_title: Optional[str] = None
    openai_model: Optional[str] = "gpt-4o"
    max_retries: Optional[int] = 3

class EvaluationResponse(BaseModel):
    success: bool
    scores: Optional[Dict[str, float]] = None
    error: Optional[str] = None

def evaluate_summary_with_llm_judge(
    summary_content: str, 
    search_query: str, 
    video_title: str = None,
    openai_api_key: str = None,
    openai_model: str = "gpt-4o",
    max_retries: int = 3
) -> Optional[Dict[str, float]]:
    """
    Evaluate a summary using an LLM judge based on relevance, helpfulness, and conciseness.
    
    Args:
        summary_content: The summary text to evaluate
        search_query: The original search query
        video_title: The video title (optional, for transcript summaries)
        openai_api_key: OpenAI API key
        openai_model: OpenAI model to use
        max_retries: Maximum number of retry attempts for rate limits
        
    Returns:
        Dictionary with scores: {'relevance': float, 'helpfulness': float, 'conciseness': float}
        or None if evaluation fails
    """
    for attempt in range(max_retries + 1):
        try:
            if not openai_api_key:
                logger.error("OpenAI API key not provided for LLM judge")
                return None
            
            # Clear any proxy environment variables that might conflict with OpenAI client
            proxy_vars = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'NO_PROXY', 'no_proxy']
            for var in proxy_vars:
                if var in os.environ:
                    del os.environ[var]
            
            logger.info("Attempting to create OpenAI client...")
            
            # Try different approaches to create the client
            try:
                # First try: minimal configuration
                client = openai.OpenAI(api_key=openai_api_key)
                logger.info("OpenAI client created successfully with minimal config")
            except Exception as e1:
                logger.warning(f"First attempt failed: {e1}")
                try:
                    # Second try: with explicit timeout
                    client = openai.OpenAI(api_key=openai_api_key, timeout=30.0)
                    logger.info("OpenAI client created successfully with timeout")
                except Exception as e2:
                    logger.warning(f"Second attempt failed: {e2}")
                    # Third try: with base_url
                    client = openai.OpenAI(api_key=openai_api_key, base_url="https://api.openai.com/v1")
                    logger.info("OpenAI client created successfully with base_url")
            
            # Create context for the judge
            context = f"Search Query: {search_query}"
            if video_title:
                context += f"\nVideo Title: {video_title}"
            
            prompt = f"""
You are an expert evaluator of product review summaries. Please evaluate the following summary based on three criteria:

{context}

Summary to evaluate:
{summary_content}

Please rate the summary on a scale of 0.0 to 5.0 for each criterion:

1. **Relevance (0.0-5.0)**: How well does the summary address the search query and provide information that a potential buyer would find relevant?

2. **Helpfulness (0.0-5.0)**: How useful is the summary for making a purchase decision? Does it provide actionable insights, pros/cons, and clear recommendations?

3. **Conciseness (0.0-5.0)**: How well does the summary balance being comprehensive while remaining concise and easy to read?

Respond with ONLY a JSON object in this exact format:
{{
    "relevance": 4.0,
    "helpfulness": 3.0,
    "conciseness": 5.0
}}

Do not include any other text or explanation, just the JSON object.
"""

            response = client.chat.completions.create(
                model=openai_model,
                messages=[
                    {"role": "system", "content": "You are an expert evaluator that provides precise numerical scores for product review summaries. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
                temperature=0.1
            )
            
            # Parse the response
            response_text = response.choices[0].message.content.strip()
            
            # Try to extract JSON from the response
            try:
                # Remove any markdown formatting if present
                if response_text.startswith('```json'):
                    response_text = response_text.replace('```json', '').replace('```', '').strip()
                elif response_text.startswith('```'):
                    response_text = response_text.replace('```', '').strip()
                
                scores = json.loads(response_text)
                
                # Validate scores are within expected range (0-5 scale)
                for key in ['relevance', 'helpfulness', 'conciseness']:
                    if key not in scores:
                        logger.error(f"Missing score for {key}")
                        return None
                    score = scores[key]
                    if not isinstance(score, (int, float)) or score < 0 or score > 5:
                        logger.error(f"Invalid score for {key}: {score} (should be 0-5)")
                        return None
                
                logger.info(f"LLM Judge scores - Relevance: {scores['relevance']:.2f}, Helpfulness: {scores['helpfulness']:.2f}, Conciseness: {scores['conciseness']:.2f}")
                return scores
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM judge response as JSON: {e}")
                logger.error(f"Response text: {response_text}")
                return None
                
        except (openai.RateLimitError, openai.APIError) as e:
            # Check if it's a rate limit error (429 status code)
            if hasattr(e, 'status_code') and e.status_code == 429:
                if attempt < max_retries:
                    # Calculate backoff time (exponential backoff with jitter)
                    backoff_time = min(2 ** attempt + (time.time() % 1), 60)  # Cap at 60 seconds
                    logger.warning(f"Rate limit hit, retrying in {backoff_time:.1f} seconds (attempt {attempt + 1}/{max_retries + 1})")
                    time.sleep(backoff_time)
                    continue
                else:
                    logger.error(f"Rate limit exceeded after {max_retries + 1} attempts: {e}")
                    return None
            else:
                # Not a rate limit error, re-raise
                raise
                
        except Exception as e:
            logger.error(f"Error in LLM judge evaluation: {e}")
            return None
    
    return None

@app.get("/")
async def root():
    return {"message": "LLM Judge API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_summary(request: EvaluationRequest):
    """
    Evaluate a summary using the LLM judge.
    """
    try:
        # Get OpenAI API key from environment
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise HTTPException(status_code=500, detail="OpenAI API key not configured")
        
        # Call the LLM judge
        scores = evaluate_summary_with_llm_judge(
            summary_content=request.summary_content,
            search_query=request.search_query,
            video_title=request.video_title,
            openai_api_key=openai_api_key,
            openai_model=request.openai_model,
            max_retries=request.max_retries
        )
        
        if scores:
            return EvaluationResponse(success=True, scores=scores)
        else:
            return EvaluationResponse(success=False, error="Failed to evaluate summary")
            
    except Exception as e:
        logger.error(f"Error in evaluate endpoint: {e}")
        return EvaluationResponse(success=False, error=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080))) 