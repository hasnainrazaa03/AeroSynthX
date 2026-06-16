"""Optimization search-strategy engines."""

from aerosynthx.optimizer.schemas import OptimizationSpec
from aerosynthx.study.schemas import StudySpec


class GridSearchEngine:
    """A deterministic grid search engine."""

    def create_study_spec(self, spec: OptimizationSpec) -> StudySpec:
        """
        Creates a StudySpec from an OptimizationSpec for a grid search.
        """
        # For a grid search, the design space directly translates to the
        # study variables.
        return StudySpec(
            study_name=f"Optimization Study for '{spec.objective}'",
            base_intent=spec.base_intent,
            variables=spec.design_space,
        )
