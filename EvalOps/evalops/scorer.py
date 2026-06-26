class Scorer:
    """
    Evaluates generated LLM responses against expected golden answers
    using traditional deterministic metrics.
    """

    @staticmethod
    def exact_match(expected: str, actual: str) -> float:
        """
        Compute exact match score (1.0 if identical after stripping whitespace, 0.0 otherwise).

        Args:
            expected (str): Golden truth string.
            actual (str): Model generated response.

        Returns:
            float: Score (0.0 or 1.0).
        """
        pass

    @staticmethod
    def fuzzy_match(expected: str, actual: str, threshold: float = 0.8) -> float:
        """
        Compute fuzzy matching score (e.g., token ratio or Levenshtein distance similarity).

        Args:
            expected (str): Golden truth string.
            actual (str): Model generated response.
            threshold (float): Score threshold for passing.

        Returns:
            float: Similarity score between 0.0 and 1.0.
        """
        pass

    @staticmethod
    def regex_match(pattern: str, actual: str) -> float:
        """
        Determine if the generated response matches a regular expression pattern.

        Args:
            pattern (str): The regex pattern to search for.
            actual (str): Model generated response.

        Returns:
            float: 1.0 if match is found, 0.0 otherwise.
        """
        pass
