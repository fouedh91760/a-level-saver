"""Base agent class for AI-powered automation."""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from anthropic import Anthropic
from config import settings

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all automation agents."""

    def __init__(self, name: str, system_prompt: str):
        self.name = name
        self.system_prompt = system_prompt
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.conversation_history: List[Dict[str, str]] = []

    def _build_messages(self, user_message: str) -> List[Dict[str, str]]:
        """Build the message list for the API call."""
        messages = self.conversation_history.copy()
        messages.append({
            "role": "user",
            "content": user_message
        })
        return messages

    def ask(
        self,
        user_message: str,
        context: Optional[Dict[str, Any]] = None,
        reset_history: bool = False
    ) -> str:
        """
        Send a message to the agent and get a response.

        Args:
            user_message: The message to send to the agent
            context: Additional context data to include
            reset_history: Whether to reset conversation history before this message

        Returns:
            The agent's response
        """
        if reset_history:
            self.conversation_history = []

        # Add context to message if provided
        if context:
            context_str = "\n\n## Context Data:\n"
            for key, value in context.items():
                context_str += f"**{key}**: {value}\n"
            full_message = context_str + "\n" + user_message
        else:
            full_message = user_message

        messages = self._build_messages(full_message)

        try:
            logger.info(f"[{self.name}] Sending request to Claude")

            response = self.client.messages.create(
                model=settings.agent_model,
                max_tokens=settings.agent_max_tokens,
                temperature=settings.agent_temperature,
                system=self.system_prompt,
                messages=messages
            )

            assistant_message = response.content[0].text

            # Update conversation history
            self.conversation_history.append({
                "role": "user",
                "content": full_message
            })
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })

            logger.info(f"[{self.name}] Received response")
            return assistant_message

        except Exception as e:
            logger.error(f"[{self.name}] Error communicating with Claude: {e}")
            raise

    def reset_conversation(self) -> None:
        """Reset the conversation history."""
        self.conversation_history = []
        logger.info(f"[{self.name}] Conversation history reset")

    @abstractmethod
    def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process data using the agent.

        This method should be implemented by each specific agent.

        Args:
            data: Input data for the agent to process

        Returns:
            Processed data/results
        """
        pass
