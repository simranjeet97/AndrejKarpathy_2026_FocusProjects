from typing import Optional, Dict, Any, List
from evalops.config import Settings

class PairwiseComparator:
    """
    Compares two evaluation runs task-by-task.
    Identifies if candidate model (Run B) has regressed or improved relative to baseline (Run A).
    """

    def __init__(self, judge_model: Optional[str] = None, settings: Optional[Settings] = None):
        """
        Initialize the pairwise comparator.

        Args:
            judge_model (str, optional): LLM model used to judge comparisons.
            settings (Settings, optional): App configuration settings.
        """
        pass

    async def compare_runs(self, run_a_id: str, run_b_id: str) -> List[Dict[str, Any]]:
        """
        Run pairwise comparisons for all tasks across two runs.

        Args:
            run_a_id (str): Baseline run ID.
            run_b_id (str): Candidate run ID.

        Returns:
            List[Dict[str, Any]]: List of pairwise comparison records containing the winner and reasoning.
        """
        pass

    async def generate_win_rates(self, run_a_id: str, run_b_id: str) -> Dict[str, float]:
        """
        Compute win rates, loss rates, and tie rates for Run B vs Run A.

        Args:
            run_a_id (str): Baseline run ID.
            run_b_id (str): Candidate run ID.

        Returns:
            Dict[str, float]: Win rate statistics (e.g. {'win': 0.6, 'loss': 0.3, 'tie': 0.1}).
        """
        pass
