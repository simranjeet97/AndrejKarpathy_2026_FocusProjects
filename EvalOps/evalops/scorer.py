import re

class EvalScorer:
    """
    Evaluates generated LLM responses against expected golden answers
    using traditional deterministic metrics.
    """

    @staticmethod
    def exact_match(output: str, expected: str) -> float:
        """
        Compute exact match score (1.0 if identical after case-insensitive strip, 0.0 otherwise).

        Args:
            output (str): Model generated response.
            expected (str): Golden truth string.

        Returns:
            float: Score (0.0 or 1.0).
        """
        if output.strip().lower() == expected.strip().lower():
            return 1.0
        return 0.0

    @staticmethod
    def contains_match(output: str, expected: str) -> float:
        """
        Compute contains match score (1.0 if expected substring is in output, 0.0 otherwise).

        Args:
            output (str): Model generated response.
            expected (str): Golden truth string.

        Returns:
            float: Score (0.0 or 1.0).
        """
        if not expected.strip():
            return 0.0
        if expected.lower() in output.lower():
            return 1.0
        return 0.0

    @staticmethod
    def _tokenize(text: str) -> set:
        """Helper to tokenize text into lowercase word tokens."""
        words = re.findall(r'\w+', text.lower())
        return set(words)

    @classmethod
    def token_overlap_score(cls, output: str, expected: str) -> float:
        """
        Compute Jaccard similarity between word tokens of output and expected answers.

        Args:
            output (str): Model generated response.
            expected (str): Golden truth string.

        Returns:
            float: Token overlap score between 0.0 and 1.0.
        """
        tokens_out = cls._tokenize(output)
        tokens_exp = cls._tokenize(expected)
        
        if not tokens_out and not tokens_exp:
            return 1.0
        
        intersection = tokens_out.intersection(tokens_exp)
        union = tokens_out.union(tokens_exp)
        return float(len(intersection)) / len(union)

    @staticmethod
    def length_penalty(output: str, expected: str, tolerance: float = 0.5) -> float:
        """
        Penalize the score if output length deviates from expected length by more than tolerance.

        Args:
            output (str): Model generated response.
            expected (str): Golden truth string.
            tolerance (float): Maximum deviation percentage without penalty (default 0.5 = 50%).

        Returns:
            float: Length penalty score between 0.0 and 1.0.
        """
        l_out = len(output)
        l_exp = len(expected)
        if l_exp == 0:
            return 1.0 if l_out == 0 else 0.0
        
        deviation_ratio = abs(l_out - l_exp) / l_exp
        if deviation_ratio <= tolerance:
            return 1.0
        
        # Penalize proportionally for deviation beyond tolerance, capping at 0.0
        return max(0.0, 1.0 - (deviation_ratio - tolerance))

    @classmethod
    def composite_score(cls, output: str, expected: str) -> float:
        """
        Calculate a composite score based on token overlap (50%), contains match (30%),
        and length penalty (20%).

        Args:
            output (str): Model generated response.
            expected (str): Golden truth string.

        Returns:
            float: Weighted score between 0.0 and 1.0.
        """
        overlap = cls.token_overlap_score(output, expected)
        contains = cls.contains_match(output, expected)
        length = cls.length_penalty(output, expected)
        
        return (0.5 * overlap) + (0.3 * contains) + (0.2 * length)
