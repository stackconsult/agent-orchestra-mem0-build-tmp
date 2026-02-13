# Contributing to Agent Orchestra

Thank you for your interest in contributing to Agent Orchestra! This guide will help you get started.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Coding Standards](#coding-standards)
5. [Testing Guidelines](#testing-guidelines)
6. [Documentation](#documentation)
7. [Submitting Changes](#submitting-changes)
8. [Review Process](#review-process)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors.

### Our Standards

- **Be respectful**: Treat others with dignity and respect
- **Be inclusive**: Welcome all perspectives and backgrounds
- **Be constructive**: Provide helpful feedback and suggestions
- **Be collaborative**: Work together to achieve common goals

### Reporting Issues

If you experience or witness unacceptable behavior, please contact conduct@agent-orchestra.com

---

## Getting Started

### Prerequisites

- Python 3.11+
- Git
- Docker (optional)
- PostgreSQL 13+
- Redis 6+

### Setup Development Environment

```bash
# 1. Fork the repository
# Click "Fork" on GitHub, then clone your fork

git clone https://github.com/YOUR_USERNAME/agent-orchestra-production-build-tmp
cd agent-orchestra-production-build-tmp

# 2. Add upstream remote
git remote add upstream https://github.com/stackconsult/agent-orchestra-production-build-tmp

# 3. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 4. Install dependencies
cd q-and-a-orchestra-agent
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 5. Setup pre-commit hooks
pre-commit install

# 6. Setup database
createdb orchestra_dev
export DATABASE_URL=postgresql://localhost/orchestra_dev
alembic upgrade head

# 7. Run tests to verify setup
pytest tests/
```

### Development Dependencies

Create `requirements-dev.txt`:

```txt
# Testing
pytest==8.3.4
pytest-asyncio==0.25.3
pytest-cov==6.0.0
pytest-mock==3.14.0

# Code quality
black==25.1.0
flake8==7.1.1
mypy==1.15.0
isort==5.13.2

# Pre-commit
pre-commit==4.0.1

# Documentation
mkdocs==1.6.1
mkdocs-material==9.5.49
```

---

## Development Workflow

### 1. Create an Issue

Before starting work:
- Check existing issues for duplicates
- Create a new issue describing the problem/feature
- Wait for approval from maintainers

### 2. Create a Branch

```bash
# Sync with upstream
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number-description
```

### 3. Make Changes

Follow the [Coding Standards](#coding-standards) and [Testing Guidelines](#testing-guidelines).

### 4. Test Your Changes

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest --cov=. tests/ --cov-report=html

# Run type checking
mypy .

# Run linting
flake8 .
black --check .
isort --check-only .

# Run security checks
safety scan
bandit -r .
```

### 5. Commit Changes

```bash
# Stage changes
git add .

# Commit with conventional commit message
git commit -m "feat: add new agent for code review"

# Push to your fork
git push origin feature/your-feature-name
```

---

## Coding Standards

### Python Style

We follow PEP 8 with additional rules:

```python
# Imports
import os
import sys
from typing import Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel

# Constants
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30

# Class definitions
class AgentOrchestrator:
    """Orchestrates multiple AI agents.
    
    This class coordinates between different specialized agents
    to handle complex tasks.
    """
    
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self._agents: List[BaseAgent] = []
    
    async def process_task(self, task: Task) -> Result:
        """Process a task using appropriate agents.
        
        Args:
            task: The task to process
            
        Returns:
            Result of processing the task
            
        Raises:
            ProcessingError: If task processing fails
        """
        try:
            agent = self._select_agent(task)
            return await agent.execute(task)
        except Exception as e:
            logger.error(f"Task processing failed: {e}")
            raise ProcessingError(f"Failed to process task: {e}")
```

### Naming Conventions

- **Variables**: `snake_case`
- **Functions**: `snake_case`
- **Classes**: `PascalCase`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private members**: `_leading_underscore`
- **Modules**: `snake_case.py`

### Type Hints

All public APIs must have type hints:

```python
from typing import Dict, List, Optional, Union

def analyze_repository(
    path: str,
    options: Optional[Dict[str, Any]] = None
) -> AnalysisResult:
    """Analyze a repository structure."""
    pass
```

### Documentation

Use docstrings for all public modules, classes, and functions:

```python
def calculate_cost(
    tokens: int,
    model: str,
    pricing: Dict[str, float]
) -> float:
    """Calculate the cost of API usage.
    
    Args:
        tokens: Number of tokens used
        model: Model identifier
        pricing: Pricing information per 1k tokens
        
    Returns:
        Total cost in USD
        
    Example:
        >>> pricing = {"input": 0.001, "output": 0.002}
        >>> calculate_cost(1000, "gpt-4", pricing)
        0.001
    """
    pass
```

---

## Testing Guidelines

### Test Structure

```
tests/
├── unit/           # Unit tests
├── integration/    # Integration tests
├── e2e/           # End-to-end tests
└── fixtures/      # Test fixtures
```

### Writing Tests

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

from agents.repository_analyzer import RepositoryAnalyzerAgent
from schemas.messages import AgentMessage

class TestRepositoryAnalyzer:
    """Test suite for RepositoryAnalyzerAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create agent instance for testing."""
        mock_client = AsyncMock()
        return RepositoryAnalyzerAgent(mock_client)
    
    @pytest.fixture
    def sample_message(self):
        """Create sample message for testing."""
        return AgentMessage(
            correlation_id="test-123",
            agent_id="test-agent",
            intent="analyze_repository",
            message_type="request",
            payload={"repository_path": "/test/repo"}
        )
    
    @pytest.mark.asyncio
    async def test_analyze_repository_success(self, agent, sample_message):
        """Test successful repository analysis."""
        # Arrange
        expected_result = {"files": 10, "languages": ["Python"]}
        
        # Act
        result = await agent.process_message(sample_message)
        
        # Assert
        assert result is not None
        assert result["status"] == "success"
        assert "analysis" in result
```

### Test Coverage

- Aim for >90% coverage on new code
- All critical paths must be tested
- Edge cases and error conditions must be covered

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_agents.py

# Run with coverage
pytest --cov=. --cov-report=html

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run tests with specific marker
pytest -m "slow"
```

---

## Documentation

### Code Documentation

- All public APIs must have docstrings
- Use Google-style docstrings
- Include examples for complex functions

### API Documentation

API documentation is generated from OpenAPI specs:

```python
from fastapi import FastAPI
from pydantic import BaseModel

class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    
    message: str
    session_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Hello, orchestra!",
                "session_id": "sess_123"
            }
        }

@app.post("/v2/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with the agent orchestra.
    
    This endpoint processes messages through the agent orchestration
    system and returns intelligent responses.
    """
    pass
```

### README Updates

When adding features:
1. Update the feature list in README
2. Add usage examples
3. Update API documentation link
4. Add new dependencies to installation guide

---

## Submitting Changes

### Commit Message Format

Use [Conventional Commits](https://conventionalcommits.org/):

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(agents): add code review agent

Implement a new agent that performs automated code reviews
with support for multiple programming languages.

Closes #123
```

```
fix(auth): resolve JWT token validation issue

The validation was failing for tokens with special characters
due to incorrect regex pattern.
```

### Pull Request Process

1. **Create Pull Request**
   ```bash
   # Push your branch
   git push origin feature/your-feature-name
   
   # Create PR on GitHub
   # Link to any relevant issues
   ```

2. **PR Template**
   ```markdown
   ## Description
   Brief description of changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update
   
   ## Testing
   - [ ] All tests pass
   - [ ] New tests added
   - [ ] Manual testing completed
   
   ## Checklist
   - [ ] Code follows style guidelines
   - [ ] Self-review completed
   - [ ] Documentation updated
   - [ ] No breaking changes (or documented)
   ```

3. **Requirements**
   - All tests must pass
   - Code coverage must not decrease
   - Documentation must be updated
   - Must pass CI checks

---

## Review Process

### Review Criteria

1. **Functionality**
   - Does the code work as intended?
   - Are edge cases handled?
   - Is error handling appropriate?

2. **Code Quality**
   - Is the code readable and maintainable?
   - Does it follow style guidelines?
   - Are there obvious improvements?

3. **Testing**
   - Are tests comprehensive?
   - Do tests cover edge cases?
   - Are tests well-written?

4. **Documentation**
   - Is documentation clear?
   - Are examples provided?
   - Is API documentation updated?

### Review Guidelines for Reviewers

1. **Be constructive**: Provide specific, actionable feedback
2. **Be respectful**: Acknowledge the effort put in
3. **Explain reasoning**: Help the author understand your perspective
4. **Suggest improvements**: Offer concrete suggestions

### Addressing Feedback

1. **Acknowledge**: Thank reviewers for their time
2. **Clarify**: Ask questions if feedback is unclear
3. **Implement**: Make requested changes
4. **Explain**: If you disagree, explain your reasoning

---

## Release Process

### Versioning

We use [Semantic Versioning](https://semver.org/):
- `MAJOR.MINOR.PATCH`
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes (backward compatible)

### Release Checklist

1. [ ] All tests passing
2. [ ] Documentation updated
3. [ ] CHANGELOG updated
4. [ ] Version bumped
5. [ ] Tag created
6. [ ] Release notes written

---

## Getting Help

### Resources

- **Documentation**: https://docs.agent-orchestra.com
- **API Reference**: https://api.agent-orchestra.com/docs
- **Discord**: https://discord.gg/agent-orchestra
- **Stack Overflow**: Use tag `agent-orchestra`

### Contact

- **Maintainers**: maintainers@agent-orchestra.com
- **Security**: security@agent-orchestra.com
- **Support**: support@agent-orchestra.com

---

## Recognition

Contributors are recognized in:
- AUTHORS file
- Release notes
- Annual contributor awards
- Special contributor badge on GitHub

Thank you for contributing to Agent Orchestra! 🎉
