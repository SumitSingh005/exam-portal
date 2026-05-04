import math
import re
from collections import Counter

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ModuleNotFoundError:
    TfidfVectorizer = None
    cosine_similarity = None


FALLBACK_STOP_WORDS = {
    'and', 'are', 'but', 'for', 'from', 'has', 'have', 'not', 'the', 'this',
    'that', 'was', 'with', 'you', 'your', 'into', 'its', 'can', 'will', 'our',
    'about', 'also', 'than', 'then', 'they', 'them', 'their',
}


def preprocess(text):
    text = (text or '').lower()
    text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    return " ".join(text.split())


def tokenize(text):
    return preprocess(text).split()


def get_stop_words():
    if TfidfVectorizer:
        return set(TfidfVectorizer(stop_words='english').get_stop_words())
    return FALLBACK_STOP_WORDS


def build_keywords(model_ans, limit=8):
    stop_words = get_stop_words()
    words = [
        word for word in tokenize(model_ans)
        if len(word) > 2 and word not in stop_words
    ]
    return [word for word, _ in Counter(words).most_common(limit)]


def get_similarity(student_ans, model_ans):
    student_ans = preprocess(student_ans)
    model_ans = preprocess(model_ans)

    if not student_ans or not model_ans:
        return 0

    if TfidfVectorizer and cosine_similarity:
        try:
            vectorizer = TfidfVectorizer(stop_words='english')
            vectors = vectorizer.fit_transform([student_ans, model_ans])
            return cosine_similarity(vectors[0], vectors[1])[0][0]
        except ValueError:
            return 0

    student_counts = Counter(tokenize(student_ans))
    model_counts = Counter(tokenize(model_ans))
    all_words = set(student_counts) | set(model_counts)
    dot_product = sum(student_counts[word] * model_counts[word] for word in all_words)
    student_norm = math.sqrt(sum(value * value for value in student_counts.values()))
    model_norm = math.sqrt(sum(value * value for value in model_counts.values()))
    return dot_product / (student_norm * model_norm) if student_norm and model_norm else 0


def keyword_score(student_ans, keywords):
    words = tokenize(student_ans)
    clean_keywords = [preprocess(keyword) for keyword in (keywords or [])]
    matched = sum(1 for keyword in clean_keywords if keyword in words)
    return matched / len(clean_keywords) if clean_keywords else 0


def evaluate_answer(student_ans, model_ans, keywords=None, max_marks=0):
    student_ans = student_ans or ''
    model_ans = model_ans or ''
    keywords = keywords or build_keywords(model_ans)

    if not student_ans.strip():
        return {
            "similarity": 0,
            "keyword_score": 0,
            "final_score": 0,
            "marks": 0,
            "feedback": "No answer provided",
            "keywords": keywords,
        }

    sim = get_similarity(student_ans, model_ans)
    key = keyword_score(student_ans, keywords)
    final_score = (0.7 * sim) + (0.3 * key)
    marks = round(final_score * max_marks, 2)

    if final_score > 0.8:
        feedback = "Excellent answer"
    elif final_score > 0.6:
        feedback = "Good answer but missing some key points"
    elif final_score > 0.4:
        feedback = "Basic understanding, needs improvement"
    else:
        feedback = "Poor answer, revise the concept"

    return {
        "similarity": round(sim, 2),
        "keyword_score": round(key, 2),
        "final_score": round(final_score, 2),
        "marks": marks,
        "feedback": feedback,
        "keywords": keywords,
    }
