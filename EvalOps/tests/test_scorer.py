from evalops.scorer import EvalScorer

def test_exact_match():
    # Case-insensitive stripped matches
    assert EvalScorer.exact_match(" Hello World  ", "hello world") == 1.0
    assert EvalScorer.exact_match("Different text", "expected text") == 0.0


def test_token_overlap():
    # Identical words
    assert EvalScorer.token_overlap_score("quick brown fox", "quick brown fox") == 1.0
    
    # Half overlap: out = {"quick", "brown"}, exp = {"quick", "fox"} -> intersection = {"quick"} (1), union = {"quick", "brown", "fox"} (3) -> 1/3 = 0.33
    score = EvalScorer.token_overlap_score("quick brown", "quick fox")
    assert abs(score - 0.3333333333333333) < 0.01
    
    # No overlap
    assert EvalScorer.token_overlap_score("apple", "banana") == 0.0


def test_length_penalty():
    # Within 50% deviation tolerance (e.g. expected = 10 chars, output = 14 chars -> deviation = 40% <= 50% -> score = 1.0)
    assert EvalScorer.length_penalty("12345678901234", "1234567890") == 1.0

    # Deviates >50% (expected = 10 chars, output = 20 chars -> deviation = 100% -> exceeds 50% by 50% -> score = 1 - 0.5 = 0.5)
    penalty_score = EvalScorer.length_penalty("12345678901234567890", "1234567890")
    assert abs(penalty_score - 0.5) < 0.01


def test_composite_score():
    # High similarity
    score = EvalScorer.composite_score("the speed of light is high", "the speed of light is high")
    assert score == 1.0

    # Intermediate match
    # output: "speed of light", expected: "the speed of light in a vacuum is fast"
    score = EvalScorer.composite_score("speed of light", "the speed of light in a vacuum is fast")
    assert 0.0 < score < 1.0


def test_contains_match():
    # True contain
    assert EvalScorer.contains_match("Hello world out there", "World") == 1.0
    # False contain
    assert EvalScorer.contains_match("Hello world out there", "mars") == 0.0
    # Empty expected substring
    assert EvalScorer.contains_match("Hello world out there", "") == 0.0
    # Whitespace expected substring
    assert EvalScorer.contains_match("Hello world out there", "   ") == 0.0

