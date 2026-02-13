"""
Domain Graph Context Source - Builds Domain Layer

StackConsulting Pattern: Extract workspace entities, relationships,
and relevant documents from repository analysis and project metadata.
"""

import os
from typing import Dict, Any, Optional, List
import pathlib
import re

from ..models import DomainContext
from ...config.security_config import validate_repo_path_security, is_safe_file

logger = __import__("logging").getLogger(__name__)

# Validate repository path to prevent path traversal
def validate_repo_path(repo_path: str) -> Optional[str]:
    """Validate and normalize repository path to prevent path traversal."""
    if not repo_path:
        return None
    
    # Use security configuration validation
    validation_result = validate_repo_path_security(repo_path)
    if not validation_result["valid"]:
        logger.warning(f"Path validation failed: {validation_result['reason']}")
        return None
    
    # Convert to absolute path within allowed base directory
    base_dir = os.getenv("ALLOWED_REPO_BASE_DIR", "/tmp/repos")
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)
    
    full_path = os.path.abspath(os.path.join(base_dir, repo_path))
    
    # Ensure the resolved path is still within base directory
    if not full_path.startswith(os.path.abspath(base_dir)):
        logger.warning(f"Path traversal attempt blocked: {repo_path}")
        return None
    
    return full_path


def build_domain_context(request_context: Dict[str, Any], repo_analyzer_client=None) -> DomainContext:
    """
    Build the Domain layer from repository analysis and project data.
    
    Args:
        request_context: Context from the request (repo_path, project_id, etc.)
        repo_analyzer_client: Optional repository analyzer client
    
    Returns:
        DomainContext with repository and project information
    """
    repo_path = request_context.get("repository_path") or request_context.get("repo_path")
    project_id = request_context.get("project_id")
    
    # Initialize with defaults
    domain_context = DomainContext(
        repo_path=repo_path,
        repo_summary=None,
        key_components={},
        related_docs={},
        project_metadata={},
        entity_relationships={},
    )
    
    # If we have a repo path, validate and analyze it
    if repo_path:
        validated_path = validate_repo_path(repo_path)
        if validated_path and os.path.exists(validated_path):
            domain_context = _analyze_repository(domain_context, validated_path, repo_analyzer_client)
            domain_context.repo_path = validated_path
        else:
            logger.warning(f"Invalid or inaccessible repository path: {repo_path}")
            domain_context.repo_summary = "Invalid repository path"
    
    # Add project metadata if available
    if project_id:
        domain_context.project_metadata.update(_get_project_metadata(project_id))
    
    # Build entity relationships
    domain_context.entity_relationships = _build_entity_relationships(domain_context)
    
    return domain_context


def _analyze_repository(
    domain_context: DomainContext,
    repo_path: str,
    repo_analyzer_client=None
) -> DomainContext:
    """
    Analyze repository structure and extract key information.
    """
    try:
        if repo_analyzer_client:
            # Use the repository analyzer agent if available
            analysis = repo_analyzer_client.get_repo_summary(repo_path=repo_path)
            if analysis:
                domain_context.repo_summary = analysis.get("summary")
                domain_context.key_components = analysis.get("components", {})
                domain_context.related_docs = analysis.get("related_docs", {})
        else:
            # Fallback to basic directory analysis
            domain_context = _basic_repo_analysis(domain_context, repo_path)
            
    except Exception as e:
        logger.warning(f"Failed to analyze repository {repo_path}: {e}")
        domain_context.repo_summary = f"Repository analysis failed: {str(e)}"
    
    return domain_context


def _basic_repo_analysis(domain_context: DomainContext, repo_path: str) -> DomainContext:
    """
    Basic repository analysis without specialized client.
    """
    try:
        # Look for key directories and files
        components = {}
        
        # Define safe file/directory patterns to check
        safe_patterns = {
            "package.json": "frontend",
            "requirements.txt": "backend",
            "pyproject.toml": "backend",
            "Dockerfile": "containerization",
            "docker-compose.yml": "orchestration",
            "migrations": "database",
            "alembic": "database",
            "README.md": "documentation",
        }
        
        # Check for safe files only
        for file_pattern, component_type in safe_patterns.items():
            file_path = os.path.join(repo_path, file_pattern)
            if os.path.isfile(file_path) and is_safe_file(file_path):  # Use security check
                if component_type == "frontend":
                    components["frontend"] = "Node.js/JavaScript project"
                elif component_type == "backend":
                    components["backend"] = "Python project"
                elif component_type == "containerization":
                    components["containerization"] = "Docker support"
                elif component_type == "orchestration":
                    components["orchestration"] = "Docker Compose setup"
                elif component_type == "database":
                    components["database"] = "Database migrations present"
        
        # Look for test directories (safe check)
        safe_test_dirs = ["tests", "test", "__tests__", "spec"]
        for test_dir in safe_test_dirs:
            test_path = os.path.join(repo_path, test_dir)
            if os.path.isdir(test_path):  # Use isdir for directories
                components["testing"] = f"Test suite in {test_dir}/"
                break
        
        # Look for documentation directory (safe check)
        doc_dirs = ["docs", "documentation"]
        related_docs = {}
        for doc_dir in doc_dirs:
            doc_path = os.path.join(repo_path, doc_dir)
            if os.path.isdir(doc_path):
                related_docs[doc_dir] = doc_path
        
        # Check for README file
        readme_path = os.path.join(repo_path, "README.md")
        if os.path.isfile(readme_path) and is_safe_file(readme_path):
            related_docs["README.md"] = readme_path
        
        # Create basic summary
        domain_context.repo_summary = f"Repository at {repo_path} with components: {', '.join(components.keys())}"
        domain_context.key_components = components
        domain_context.related_docs = related_docs
        
    except Exception as e:
        logger.error(f"Basic repository analysis failed: {e}")
        domain_context.repo_summary = "Unable to analyze repository"
    
    return domain_context


def _get_project_metadata(project_id: str) -> Dict[str, Any]:
    """
    Get project metadata from various sources.
    
    In a real implementation, this would query:
    - Project database
    - Configuration files
    - CI/CD metadata
    - Team directories
    """
    # Mock implementation - in production, fetch from actual sources
    metadata = {
        "project_id": project_id,
        "created_at": "2024-01-01T00:00:00Z",
        "team_size": 5,
        "tech_stack": ["python", "fastapi", "postgresql"],
        "deployment_target": "aws",
        "compliance_requirements": ["SOC2", "GDPR"],
    }
    
    return metadata


def _build_entity_relationships(domain_context: DomainContext) -> Dict[str, List[str]]:
    """
    Build relationships between entities in the domain.
    """
    relationships = {}
    
    # Component relationships
    if domain_context.key_components:
        components = list(domain_context.key_components.keys())
        relationships["components"] = components
        
        # Infer relationships based on component types
        if "frontend" in components and "backend" in components:
            relationships["frontend_backend"] = ["frontend", "backend"]
        
        if "database" in components and "backend" in components:
            relationships["backend_database"] = ["backend", "database"]
    
    # Document relationships
    if domain_context.related_docs:
        relationships["documentation"] = list(domain_context.related_docs.keys())
    
    # Project metadata relationships
    if domain_context.project_metadata:
        tech_stack = domain_context.project_metadata.get("tech_stack", [])
        if tech_stack:
            relationships["technologies"] = tech_stack
    
    return relationships


def enrich_domain_context(
    domain_context: DomainContext,
    rag_results: Optional[Dict[str, Any]] = None,
    knowledge_graph: Optional[Dict[str, Any]] = None
) -> DomainContext:
    """
    Enrich domain context with RAG results and knowledge graph data.
    
    Args:
        domain_context: Existing domain context
        rag_results: Optional RAG retrieval results
        knowledge_graph: Optional knowledge graph data
    
    Returns:
        Enriched DomainContext
    """
    if rag_results:
        # Add RAG results to related docs
        for doc_id, content in rag_results.items():
            domain_context.related_docs[f"rag_{doc_id}"] = content
    
    if knowledge_graph:
        # Merge knowledge graph relationships
        existing_rels = domain_context.entity_relationships
        for entity, relations in knowledge_graph.items():
            if entity in existing_rels:
                existing_rels[entity].extend(relations)
            else:
                existing_rels[entity] = relations
    
    return domain_context
