"""Collectors: plugins that each observe one kind of signal about an app run.

Import the concrete collectors from their modules; this package only exposes
the contract so the runner and tests have one place to import it from.
"""

from compatsentinel.collectors.base import Collector, CollectorSkipped, RunContext, run_collector

__all__ = ["Collector", "CollectorSkipped", "RunContext", "run_collector"]
