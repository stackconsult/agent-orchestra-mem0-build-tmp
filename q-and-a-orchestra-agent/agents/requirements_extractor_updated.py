# agents/requirements_extractor_updated.py
"""
Requirements Extraction Agent - Conducts conversational Q&A to extract user requirements.
Updated to use ModelRouter for local-first model selection.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from core.model_router import ModelRouter
from core.task_profiles import TaskProfile
from schemas.messages import AgentMessage, MessageType, RequirementsPayload
from schemas.requirements import (
    UserRequirements, RequirementsExtractionSession, 
    REQUIREMENT_QUESTIONS, QuestionTemplate, StackType, Complexity
)

logger = logging.getLogger(__name__)


class RequirementsExtractorAgent:
    """Extracts requirements from users through conversational Q&A."""
    
    def __init__(self, model_router: ModelRouter):
        self.model_router = model_router
        self.agent_id = "requirements_extractor"
        
        # Active sessions
        self._active_sessions: Dict[UUID, RequirementsExtractionSession] = {}
        
        # Question templates
        self._question_templates = {q.question_id: q for q in REQUIREMENT_QUESTIONS}
    
    async def start_extraction_session(self, message: AgentMessage) -> AgentMessage:
        """
        Start a new requirements extraction session.
        
        Args:
            message: Message to start the session
            
        Returns:
            Message with first question
        """
        try:
            session_id = message.session_id or UUID()
            
            # Create new session
            session = RequirementsExtractionSession(
                session_id=session_id,
                extraction_strategy=message.payload.get("strategy", "comprehensive"),
                focus_areas=message.payload.get("focus_areas", [])
            )
            
            self._active_sessions[session_id] = session
            
            # Get first question
            first_question = await self._get_next_question(session)
            
            # Update session
            session.questions_asked.append(first_question.question_id)
            session.current_question_index += 1
            
            # Create response
            response_message = AgentMessage(
                correlation_id=message.correlation_id,
                agent_id=self.agent_id,
                intent="question_asked",
                message_type=MessageType.QUESTION_ASKED,
                payload={
                    "question_id": first_question.question_id,
                    "question_text": first_question.question_text,
                    "question_type": first_question.question_type,
                    "examples": first_question.examples,
                    "session_progress": {
                        "current_question": session.current_question_index,
                        "total_questions": len(self._question_templates),
                        "completion_percentage": (session.current_question_index / len(self._question_templates)) * 100
                    }
                },
                session_id=session_id
            )
            
            logger.info(f"Started requirements extraction session: {session_id}")
            return response_message
            
        except Exception as e:
            logger.error(f"Failed to start extraction session: {str(e)}", exc_info=True)
            return self._create_error_message(message, str(e))
    
    async def process_answer(self, message: AgentMessage) -> AgentMessage:
        """
        Process user's answer and ask next question or complete extraction.
        
        Args:
            message: Message containing user's answer
            
        Returns:
            Message with next question or completed requirements
        """
        try:
            session_id = message.session_id
            
            if session_id not in self._active_sessions:
                return self._create_error_message(message, "No active session found")
            
            session = self._active_sessions[session_id]
            
            # Process the answer
            answer = message.payload.get("answer", "")
            question_id = message.payload.get("question_id")
            
            if question_id:
                session.answers[question_id] = answer
            
            # Check if extraction is complete
            if session.current_question_index >= len(self._question_templates):
                return await self._complete_extraction(session, message)
            
            # Get next question
            next_question = await self._get_next_question(session)
            
            # Update session
            session.questions_asked.append(next_question.question_id)
            session.current_question_index += 1
            
            # Create response
            response_message = AgentMessage(
                correlation_id=message.correlation_id,
                agent_id=self.agent_id,
                intent="question_asked",
                message_type=MessageType.QUESTION_ASKED,
                payload={
                    "question_id": next_question.question_id,
                    "question_text": next_question.question_text,
                    "question_type": next_question.question_type,
                    "examples": next_question.examples,
                    "session_progress": {
                        "current_question": session.current_question_index,
                        "total_questions": len(self._question_templates),
                        "completion_percentage": (session.current_question_index / len(self._question_templates)) * 100
                    }
                },
                session_id=session_id
            )
            
            return response_message
            
        except Exception as e:
            logger.error(f"Failed to process answer: {str(e)}", exc_info=True)
            return self._create_error_message(message, str(e))
    
    async def _get_next_question(self, session: RequirementsExtractionSession) -> QuestionTemplate:
        """Get the next question to ask using the model router."""
        try:
            # Create task profile for question selection
            task_profile = TaskProfile(
                task_type="qa",
                criticality="medium",
                latency_sensitivity="medium",
                context_size=2000,
                tool_use_required=False,
                budget_sensitivity="high"
            )
            
            # Build context for model
            context = f"""
            You are a requirements extraction assistant. Based on the current session state, 
            select the most appropriate next question to ask.
            
            Session Strategy: {session.extraction_strategy}
            Focus Areas: {', '.join(session.focus_areas) if session.focus_areas else 'None'}
            Questions Asked: {', '.join(session.questions_asked) if session.questions_asked else 'None'}
            Current Progress: {session.current_question_index}/{len(self._question_templates)}
            
            Available Questions:
            {self._format_available_questions(session)}
            
            Select the best next question ID from the available options. Consider:
            1. Logical flow of requirements gathering
            2. User's focus areas
            3. Questions already asked
            4. Session strategy
            
            Return only the question ID.
            """
            
            messages = [{"role": "user", "content": context}]
            
            # Use model router to select next question
            result = await self.model_router.select_and_invoke(
                task_profile, messages, max_tokens=100
            )
            
            # Extract question ID from response
            question_id = result.get("content", "").strip().lower()
            
            # Find the question template
            if question_id in self._question_templates:
                return self._question_templates[question_id]
            
            # Fallback to next unasked question
            for q_id, template in self._question_templates.items():
                if q_id not in session.questions_asked:
                    return template
            
            # Default fallback
            return list(self._question_templates.values())[0]
            
        except Exception as e:
            logger.error(f"Error getting next question: {e}")
            # Fallback to simple sequential selection
            unasked_questions = [q for q in self._question_templates.keys() 
                                if q not in session.questions_asked]
            if unasked_questions:
                return self._question_templates[unasked_questions[0]]
            return list(self._question_templates.values())[0]
    
    async def _complete_extraction(self, session: RequirementsExtractionSession, original_message: AgentMessage) -> AgentMessage:
        """Complete the extraction and generate final requirements using the model router."""
        try:
            # Create task profile for requirements synthesis
            task_profile = TaskProfile(
                task_type="summarization",
                criticality="high",
                latency_sensitivity="medium",
                context_size=4000,
                tool_use_required=False,
                budget_sensitivity="medium"
            )
            
            # Compile all answers
            answers_text = "\n".join([
                f"Q: {self._question_templates[q_id].question_text}\nA: {answer}"
                for q_id, answer in session.answers.items()
            ])
            
            prompt = f"""
            Based on the following Q&A session, extract and structure the user's requirements:
            
            Session Strategy: {session.extraction_strategy}
            Focus Areas: {', '.join(session.focus_areas) if session.focus_areas else 'None'}
            
            Q&A Session:
            {answers_text}
            
            Extract and structure the requirements into:
            1. Functional Requirements
            2. Non-Functional Requirements  
            3. Technical Constraints
            4. User Stories/Use Cases
            5. Success Criteria
            
            Format as JSON with clear structure.
            """
            
            messages = [{"role": "user", "content": prompt}]
            
            # Use model router to synthesize requirements
            result = await self.model_router.select_and_invoke(
                task_profile, messages, max_tokens=2000
            )
            
            # Parse the response into UserRequirements
            requirements_content = result.get("content", "")
            
            # Create requirements object (simplified parsing)
            requirements = UserRequirements(
                project_name="Extracted Requirements",
                description=requirements_content,
                functional_requirements=[],
                non_functional_requirements=[],
                technical_constraints=[],
                user_stories=[],
                success_criteria=[],
                estimated_complexity=Complexity.MEDIUM,
                preferred_stack=StackType.PYTHON  # Default
            )
            
            # Clean up session
            del self._active_sessions[session.session_id]
            
            # Create completion message
            response_message = AgentMessage(
                correlation_id=original_message.correlation_id,
                agent_id=self.agent_id,
                intent="extraction_complete",
                message_type=MessageType.EXTRACTION_COMPLETE,
                payload={
                    "requirements": requirements.dict(),
                    "session_summary": {
                        "total_questions": len(self._question_templates),
                        "questions_asked": len(session.questions_asked),
                        "completion_rate": (len(session.questions_asked) / len(self._question_templates)) * 100
                    }
                },
                session_id=session.session_id
            )
            
            logger.info(f"Completed requirements extraction for session: {session.session_id}")
            return response_message
            
        except Exception as e:
            logger.error(f"Failed to complete extraction: {str(e)}", exc_info=True)
            return self._create_error_message(original_message, str(e))
    
    def _format_available_questions(self, session: RequirementsExtractionSession) -> str:
        """Format available questions for model context."""
        available = []
        for q_id, template in self._question_templates.items():
            if q_id not in session.questions_asked:
                available.append(f"{q_id}: {template.question_text}")
        return "\n".join(available)
    
    def _create_error_message(self, original_message: AgentMessage, error: str) -> AgentMessage:
        """Create an error response message."""
        return AgentMessage(
            correlation_id=original_message.correlation_id,
            agent_id=self.agent_id,
            intent="error",
            message_type=MessageType.ERROR,
            payload={"error": error},
            session_id=original_message.session_id
        )
