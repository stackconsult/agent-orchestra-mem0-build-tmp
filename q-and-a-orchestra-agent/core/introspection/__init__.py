"""
Model Introspection Module

This module provides automatic model discovery and profiling capabilities
for the Agent Orchestra Local LLM Router v2.

Components:
- ModelInspector: Discovers models from various providers
- BenchmarkSuite: Evaluates model capabilities
- ModelProfile: Stores model metadata and benchmarks
- DiscoveryOrchestrator: Coordinates parallel discovery
"""

from .model_inspector import ModelInspector
from .benchmarks import BenchmarkSuite, BenchmarkResult
from .model_profile import ModelProfile, ModelCapabilities
from .discovery_orchestrator import DiscoveryOrchestrator

__all__ = [
    "ModelInspector",
    "BenchmarkSuite", 
    "BenchmarkResult",
    "ModelProfile",
    "ModelCapabilities",
    "DiscoveryOrchestrator"
]
