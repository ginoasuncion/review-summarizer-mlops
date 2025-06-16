from collections import Counter

def summarize_feedback(reviews: list[str]) -> str:
    words = " ".join(reviews).lower().split()
    top_words = Counter(words).most_common(3)
    return "Top words: " + ", ".join([word for word, _ in top_words])

