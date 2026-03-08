def evaluate_answer(answer: str, expected_terms: list[str]) -> float:
    if not expected_terms:
        return 0.0
    answer_lower = answer.lower()
    matched = sum(1 for term in expected_terms if term.lower() in answer_lower)
    return matched / len(expected_terms)