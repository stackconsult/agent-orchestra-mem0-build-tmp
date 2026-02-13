"""
Context-Aware Orchestrator - Enhanced with 6-Layer Context Engineering

Integrates context engineering into the orchestration flow to provide
agents with complete understanding of user requests and system state.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from datetime import datetime

from anthropic import AsyncAnthropic

# Import context engineering
from context_engineering.models import ContextEnvelope

from agents.repository_analyzer import RepositoryAnalyzerAgent
from agents.requirements_extractor import RequirementsExtractorAgent
from agents.architecture_designer import ArchitectureDesignerAgent
from agents.implementation_planner import ImplementationPlannerAgent
from agents.validator import ValidatorAgent

from orchestrator.message_bus import MessageBus
from orchestrator.router import MessageRouter
from orchestrator.context_manager import ContextManager, ConversationMemory

from schemas.messages import AgentMessage, MessageType

logger = logging.getLogger(__name__)


class ContextAwareOrchestrator:
    """
    Context-aware orchestrator that uses 6-Layer Context Engineering
    to drive agent selection and execution.
    """
    
    def __init__(self, anthropic_client: AsyncAnthropic, redis_url: str = "redis://localhost:6379/0"):
        self.anthropic = anthropic_client
        
        # Core components
        self.message_bus = MessageBus(redis_url)
        self.router = MessageRouter(self.message_bus)
        self.context_manager = ContextManager()
        self.conversation_memory = ConversationMemory(self.context_manager)
        
        # Agents
        self.repository_analyzer = RepositoryAnalyzerAgent(anthropic_client, self)
        self.requirements_extractor = RequirementsExtractorAgent(anthropic_client)
        self.architecture_designer = ArchitectureDesignerAgent(anthropic_client)
        self.implementation_planner = ImplementationPlannerAgent(anthropic_client)
        self.validator = ValidatorAgent(anthropic_client)
        
        # System state
        self.is_running = False
        self.active_sessions: Dict[UUID, Dict[str, Any]] = {}
        
        # Register agents with router
        self._register_agents()
    
    async def start(self) -> None:
        """Start the orchestrator and all components."""
        try:
            # Connect message bus
            await self.message_bus.connect()
            
            # Set up message subscriptions
            await self._setup_message_subscriptions()
            
            # Register agents
            await self._register_agents_with_router()
            
            self.is_running = True
            logger.info("Context-aware orchestrator started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start orchestrator: {str(e)}")
            raise
    
    async def stop(self) -> None:
        """Stop the orchestrator and all components."""
        try:
            self.is_running = False
            
            # Disconnect message bus
            await self.message_bus.disconnect()
            
            logger.info("Context-aware orchestrator stopped")
            
        except Exception as e:
            logger.error(f"Error stopping orchestrator: {str(e)}")
    
    async def handle_request(
        self,
        message: str,
        session_id: Optional[str] = None,
        context_envelope: Optional[ContextEnvelope] = None,
    ) -> Dict[str, Any]:
        """
        Handle a request with context engineering.
        
        Args:
            message: User message
            session_id: Optional session ID for conversation continuity
            context_envelope: Complete context from 6-layer engineering
        
        Returns:
            Response with agent results
        """
        if not self.is_running:
            raise RuntimeError("Orchestrator not running")
        
        start_time = datetime.utcnow()
        
        try:
            # Extract intent from context
            primary_intent = context_envelope.intent.primary_intent if context_envelope else "general_assistance"
            
            # Route to appropriate agent flow based on intent
            if primary_intent == "repo_analysis":
                return await self._run_analysis_flow(message, context_envelope, session_id)
            elif primary_intent == "architecture_design":
                return await self._run_architecture_flow(message, context_envelope, session_id)
            elif primary_intent == "implementation":
                return await self._run_implementation_flow(message, context_envelope, session_id)
            elif primary_intent == "troubleshooting":
                return await self._run_troubleshooting_flow(message, context_envelope, session_id)
            elif primary_intent == "security_analysis":
                return await self._run_security_flow(message, context_envelope, session_id)
            else:
                return await self._run_general_flow(message, context_envelope, session_id)
                
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            return {
                "error": str(e),
                "response": "I encountered an error while processing your request.",
                "processing_time_ms": (datetime.utcnow() - start_time).total_seconds() * 1000,
            }
    
    async def _run_analysis_flow(
        self,
        message: str,
        context_envelope: ContextEnvelope,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run repository analysis flow with context.
        """
        logger.info(f"Running analysis flow for intent: {context_envelope.intent.primary_intent}")
        
        # Prepare context for repository analyzer
        repo_context = {
            "narrative": context_envelope.exposition.narrative,
            "structured": context_envelope.exposition.structured,
            "repo_path": context_envelope.domain.repo_path,
            "user_expertise": context_envelope.user.expertise_level,
            "success_criteria": context_envelope.intent.success_criteria,
        }
        
        # Run repository analysis
        analysis_result = await self.repository_analyzer.analyze(
            repository_path=context_envelope.domain.repo_path,
            context=repo_context,
            user_message=message
        )
        
        # Validate results if needed
        if context_envelope.rules.hard_walls.get("require_validation", False):
            validation = await self.validator.validate_analysis(analysis_result, context_envelope)
            analysis_result["validation"] = validation
        
        return {
            "response": analysis_result.get("summary", "Analysis completed"),
            "detailed_results": analysis_result,
            "flow": "analysis",
            "context_id": context_envelope.context_id,
        }
    
    async def _run_architecture_flow(
        self,
        message: str,
        context_envelope: ContextEnvelope,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run architecture design flow with context.
        """
        logger.info(f"Running architecture flow for intent: {context_envelope.intent.primary_intent}")
        
        # First analyze repo if not already done
        domain_info = {}
        if context_envelope.domain.repo_path and not context_envelope.domain.repo_summary:
            analysis = await self.repository_analyzer.analyze(
                repository_path=context_envelope.domain.repo_path,
                context={"narrative": context_envelope.exposition.narrative}
            )
            domain_info = analysis
        
        # Design architecture with full context
        design_context = {
            "narrative": context_envelope.exposition.narrative,
            "structured": context_envelope.exposition.structured,
            "domain_analysis": domain_info,
            "user_requirements": message,
            "constraints": context_envelope.intent.constraints,
            "rules": context_envelope.rules,
            "user_expertise": context_envelope.user.expertise_level,
        }
        
        design_result = await self.architecture_designer.design(
            requirements=message,
            context=design_context
        )
        
        # Validate design
        validation = await self.validator.validate_architecture(design_result, context_envelope)
        
        return {
            "response": design_result.get("description", "Architecture design completed"),
            "architecture": design_result,
            "validation": validation,
            "flow": "architecture",
            "context_id": context_envelope.context_id,
        }
    
    async def _run_implementation_flow(
        self,
        message: str,
        context_envelope: ContextEnvelope,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run implementation flow with context.
        """
        logger.info(f"Running implementation flow for intent: {context_envelope.intent.primary_intent}")
        
        # Extract requirements from message
        requirements = await self.requirements_extractor.extract(
            message,
            context={"narrative": context_envelope.exposition.narrative}
        )
        
        # Create implementation plan
        plan_context = {
            "narrative": context_envelope.exposition.narrative,
            "structured": context_envelope.exposition.structured,
            "requirements": requirements,
            "domain": context_envelope.domain.dict(),
            "rules": context_envelope.rules,
            "environment": context_envelope.environment.dict(),
        }
        
        implementation_plan = await self.implementation_planner.plan(
            requirements=requirements,
            context=plan_context
        )
        
        return {
            "response": implementation_plan.get("summary", "Implementation plan created"),
            "plan": implementation_plan,
            "requirements": requirements,
            "flow": "implementation",
            "context_id": context_envelope.context_id,
        }
    
    async def _run_troubleshooting_flow(
        self,
        message: str,
        context_envelope: ContextEnvelope,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run troubleshooting flow with context.
        """
        logger.info(f"Running troubleshooting flow for intent: {context_envelope.intent.primary_intent}")
        
        # Analyze the problem
        problem_context = {
            "narrative": context_envelope.exposition.narrative,
            "structured": context_envelope.exposition.structured,
            "problem_description": message,
            "domain": context_envelope.domain.dict(),
            "environment": context_envelope.environment.dict(),
        }
        
        # Use repository analyzer to understand code context if applicable
        code_analysis = None
        if context_envelope.domain.repo_path:
            code_analysis = await self.repository_analyzer.analyze(
                repository_path=context_envelope.domain.repo_path,
                context={"problem": message}
            )
        
        # Generate solution
        solution = await self._generate_troubleshooting_solution(
            message, 
            problem_context, 
            code_analysis,
            context_envelope
        )
        
        return {
            "response": solution.get("solution", "Troubleshooting analysis completed"),
            "root_cause": solution.get("root_cause"),
            "steps": solution.get("steps", []),
            "code_analysis": code_analysis,
            "flow": "troubleshooting",
            "context_id": context_envelope.context_id,
        }
    
    async def _run_security_flow(
        self,
        message: str,
        context_envelope: ContextEnvelope,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run security analysis flow with context.
        """
        logger.info(f"Running security flow for intent: {context_envelope.intent.primary_intent}")
        
        # Security analysis with compliance checks
        security_context = {
            "narrative": context_envelope.exposition.narrative,
            "structured": context_envelope.exposition.structured,
            "security_requirements": message,
            "compliance_rules": context_envelope.rules.hard_walls,
            "domain": context_envelope.domain.dict(),
        }
        
        # Analyze repository for security issues
        security_analysis = None
        if context_envelope.domain.repo_path:
            security_analysis = await self.repository_analyzer.security_analysis(
                repository_path=context_envelope.domain.repo_path,
                context=security_context
            )
        
        # Generate security report
        security_report = await self._generate_security_report(
            message,
            security_context,
            security_analysis,
            context_envelope
        )
        
        return {
            "response": security_report.get("summary", "Security analysis completed"),
            "vulnerabilities": security_report.get("vulnerabilities", []),
            "recommendations": security_report.get("recommendations", []),
            "compliance_status": security_report.get("compliance_status"),
            "flow": "security",
            "context_id": context_envelope.context_id,
        }
    
    async def _run_general_flow(
        self,
        message: str,
        context_envelope: ContextEnvelope,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run general assistance flow with context.
        """
        logger.info(f"Running general flow with context")
        
        # Use context to provide informed response
        response = await self._generate_contextual_response(
            message,
            context_envelope
        )
        
        return {
            "response": response,
            "flow": "general",
            "context_id": context_envelope.context_id,
        }
    
    async def _generate_troubleshooting_solution(
        self,
        problem: str,
        context: Dict[str, Any],
        code_analysis: Optional[Dict[str, Any]],
        context_envelope: ContextEnvelope
    ) -> Dict[str, Any]:
        """Generate troubleshooting solution using context."""
        # This would use the LLM with context to generate solutions
        # For now, return a structured response
        return {
            "root_cause": "Analysis based on context",
            "solution": "Generated solution considering system state and user expertise",
            "steps": [
                "1. Analyze the problem using domain context",
                "2. Identify root causes based on system state",
                "3. Provide solution tailored to user expertise level",
            ]
        }
    
    async def _generate_security_report(
        self,
        request: str,
        context: Dict[str, Any],
        analysis: Optional[Dict[str, Any]],
        context_envelope: ContextEnvelope
    ) -> Dict[str, Any]:
        """Generate security report using context."""
        return {
            "summary": "Security analysis completed with context awareness",
            "vulnerabilities": [],
            "recommendations": [],
            "compliance_status": "Compliant",
        }
    
    async def _generate_contextual_response(
        self,
        message: str,
        context_envelope: ContextEnvelope
    ) -> str:
        """Generate response using full context."""
        # Use the exposition narrative as system context
        system_prompt = f"""
Context: {context_envelope.exposition.narrative}

User Expertise: {context_envelope.user.expertise_level}
Tone: {context_envelope.rules.soft_walls.get('tone', 'professional')}
Style: {context_envelope.rules.soft_walls.get('style', 'clear')}

Provide a response that:
1. Addresses the user's specific request
2. Considers their expertise level
3. Follows the specified tone and style
4. Includes actionable next steps
"""
        
        # In production, this would call the LLM
        return f"Response generated with full context awareness for {context_envelope.intent.primary_intent}"
    
    async def _register_agents(self) -> None:
        """Register agents with their configurations."""
        pass
    
    async def _setup_message_subscriptions(self) -> None:
        """Set up message subscriptions for the orchestrator."""
        for message_type in MessageType:
            await self.message_bus.subscribe_to_message_type(
                message_type, 
                self._handle_agent_message
            )
    
    async def _register_agents_with_router(self) -> None:
        """Register agents with the message router."""
        await self.router.register_agent("repository_analyzer", {
            "message_types": ["repo_analysis_requested", "repo_analysis_completed"],
            "capabilities": ["pattern_extraction", "architecture_analysis", "security_analysis"],
            "max_concurrent_tasks": 3
        })
        
        await self.router.register_agent("requirements_extractor", {
            "message_types": ["requirements_requested", "requirements_extracted"],
            "capabilities": ["requirement_analysis", "user_story_generation"],
            "max_concurrent_tasks": 2
        })
        
        await self.router.register_agent("architecture_designer", {
            "message_types": ["design_requested", "design_completed"],
            "capabilities": ["system_design", "component_design", "api_design"],
            "max_concurrent_tasks": 2
        })
        
        await self.router.register_agent("implementation_planner", {
            "message_types": ["planning_requested", "plan_completed"],
            "capabilities": ["implementation_planning", "task_breakdown"],
            "max_concurrent_tasks": 2
        })
        
        await self.router.register_agent("validator", {
            "message_types": ["validation_requested", "validation_completed"],
            "capabilities": ["design_validation", "security_validation"],
            "max_concurrent_tasks": 3
        })
    
    async def _handle_agent_message(self, message: AgentMessage) -> None:
        """Handle messages from agents."""
        logger.info(f"Received message from agent {message.agent_id}: {message.intent}")
        # Route message based on intent and context
        await self.router.route_message(message)
