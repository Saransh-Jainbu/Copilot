"""
Ops: MLflow Experiment Tracker
Tracks experiments, prompt versions, and evaluation metrics.
"""

import logging
import os
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MLflowTracker:
    """Tracks debugging experiments using MLflow.

    Logs: prompt version, model used, input/output, latency, token count,
    and evaluation metrics.
    """

    def __init__(
        self,
        tracking_uri: str = "mlruns",
        experiment_name: str = "devops-copilot",
    ):
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name
        self._initialized = False

    def _init_mlflow(self):
        """Lazy-initialize MLflow."""
        if self._initialized:
            return
        try:
            import mlflow
            mlflow.set_tracking_uri(self.tracking_uri)
            mlflow.set_experiment(self.experiment_name)
            self._initialized = True
            logger.info(f"MLflow initialized: uri={self.tracking_uri}, experiment={self.experiment_name}")
        except ImportError:
            logger.warning("MLflow not installed. Tracking disabled.")
            self._initialized = False

    def log_debug_run(
        self,
        input_log: str,
        classification: dict,
        diagnosis: str,
        model_used: str,
        prompt_version: str,
        latency_ms: int,
        tokens_used: int,
        evaluation_scores: Optional[dict[str, float]] = None,
    ) -> Optional[str]:
        """Log a complete debugging run to MLflow.

        Args:
            input_log: The raw CI/CD log (truncated for storage).
            classification: Classification result dict.
            diagnosis: LLM-generated diagnosis text.
            model_used: Model name used for generation.
            prompt_version: Version of the prompt template used.
            latency_ms: Total latency in milliseconds.
            tokens_used: Estimated token count.
            evaluation_scores: Optional dict of metric_name -> score.

        Returns:
            MLflow run ID, or None if tracking is disabled.
        """
        self._init_mlflow()
        if not self._initialized:
            return None

        try:
            import mlflow

            with mlflow.start_run() as run:
                # Parameters
                mlflow.log_param("model", model_used)
                mlflow.log_param("prompt_version", prompt_version)
                mlflow.log_param("error_category", classification.get("category", "unknown"))
                mlflow.log_param("classification_confidence", classification.get("confidence", 0))

                # Metrics
                mlflow.log_metric("latency_ms", latency_ms)
                mlflow.log_metric("tokens_used", tokens_used)
                mlflow.log_metric("input_length", len(input_log))
                mlflow.log_metric("output_length", len(diagnosis))

                if evaluation_scores:
                    for metric_name, score in evaluation_scores.items():
                        mlflow.log_metric(f"eval_{metric_name}", score)

                # Artifacts (text files)
                mlflow.log_text(input_log[:5000], "input_log.txt")
                mlflow.log_text(diagnosis, "diagnosis.txt")

                logger.info(f"Logged MLflow run: {run.info.run_id}")
                return run.info.run_id

        except Exception as e:
            logger.error(f"Failed to log to MLflow: {e}")
            return None

    def get_experiment_summary(self) -> dict:
        """Get a summary of all runs in the current experiment."""
        self._init_mlflow()
        if not self._initialized:
            return {"error": "MLflow not initialized"}

        try:
            import mlflow

            experiment = mlflow.get_experiment_by_name(self.experiment_name)
            if not experiment:
                return {"total_runs": 0}

            runs = mlflow.search_runs(
                experiment_ids=[experiment.experiment_id],
                order_by=["start_time DESC"],
                max_results=100,
            )

            return {
                "total_runs": len(runs),
                "columns": list(runs.columns) if not runs.empty else [],
                "latest_runs": runs.head(10).to_dict(orient="records") if not runs.empty else [],
            }

        except Exception as e:
            logger.error(f"Failed to get experiment summary: {e}")
            return {"error": str(e)}
