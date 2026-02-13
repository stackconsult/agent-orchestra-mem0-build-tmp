"""
Domain Graph Context Source - Builds Domain Layer

StackConsulting Pattern: Extract workspace entities, relationships,
and relevant documents from repository analysis and project metadata.
"""

from typing import Dict, Any, Optional, List
import os

from ..models import DomainContext

logger = __import__("logging").getLogger(__name__)


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
    
    # If we have a repo path, analyze it
    if repo_path and os.path.exists(repo_path):
        domain_context = _analyze_repository(domain_context, repo_path, repo_analyzer_client)
    
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
        
        # Check for common framework indicators
        if os.path.exists(os.path.join(repo_path, "package.json")):
            components["frontend"] = "Node.js/JavaScript project"
        if os.path.exists(os.path.join(repo_path, "requirements.txt")) or os.path.exists(os.path.join(repo_path, "pyproject.toml")):
            components["backend"] = "Python project"
        if os.path.exists(os.path.join(repo_path, "Dockerfile")):
            components["containerization"] = "Docker support"
        if os.path.exists(os.path.join(repo_path, "docker-compose.yml")):
            components["orchestration"] = "Docker Compose setup"
        
        # Look for database directories
        if os.path.exists(os.path.join(repo_path, "migrations")) or os.path.exists(os.path.join(repo_path, "alembic")):
            components["database"] = "Database migrations present"
        
        # Look for test directories
        test_dirs = ["tests", "test", "__tests__", "spec"]
        for test_dir in test_dirs:
            if os.path.exists(os.path.join(repo_path, test_dir)):
                components["testing"] = f"Test suite in {test_dir}/"
                break
        
        # Look for documentation
        doc_files = ["README.md", "docs/", "documentation/"]
        related_docs = {}
        for doc in doc_files:
            if os.path.exists(os.path.join(repo_path, doc)):
                related_docs[doc] = os.path.join(repo_path, doc)
        
        # Create basic summary
        domain_context.repo_summary = f"Repository at {repo_path} with components: {', '.join(components.keys())}"
        domain_context.key_components = components
        domain_context.related_docs = related_docs
        
    except Exception as e:
        logger.error(f"Basic repository analysis failed: {e}")
        domain_context.repo_summary = f"Unable to analyze repository: {str(e)}"
    
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
