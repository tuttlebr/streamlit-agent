import logging
from datetime import datetime
from typing import Dict, List, Optional

from utils.config import config


class SystemPromptManager:
    """Manages system prompt generation with caching and consistency"""

    def __init__(self):
        self._cached_prompt: Optional[str] = None
        self._cached_tools_list: Optional[str] = None
        self._cached_date: Optional[str] = None
        self._last_cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes cache
        self._context_prompts: Dict[str, str] = {}

    def get_system_prompt(self, force_refresh: bool = False) -> str:
        """
        Get the system prompt with intelligent caching

        Args:
            force_refresh: Force refresh of cached prompt

        Returns:
            The complete system prompt
        """
        # Check if we need to refresh the cache
        if self._should_refresh_cache(force_refresh):
            self._refresh_cache()

        return self._cached_prompt

    def get_context_system_prompt(self, context: str, **kwargs) -> str:
        """
        Get a system prompt for a specific context while maintaining core persona

        Args:
            context: The context type (e.g., 'translation', 'text_processing', 'image_generation')
            **kwargs: Context-specific parameters

        Returns:
            Context-specific system prompt that maintains core persona
        """
        # Get context-specific instructions
        context_instructions = self._get_context_instructions(context, **kwargs)

        # Get tools list
        tools_list = self._get_available_tools_list()

        # Build the complete prompt with context instructions
        return self._build_system_prompt(
            tools_list=tools_list, context_instructions=context_instructions
        )

    def _get_context_instructions(self, context: str, **kwargs) -> str:
        """Get context-specific instructions by finding tools that support this context"""

        try:
            # Get tool from registry that supports this context
            from tools.registry import get_tool_by_context

            tool = get_tool_by_context(context)

            if tool:
                # Get the tool's description and parameters
                tool_def = tool.get_definition()
                description = tool_def.get("function", {}).get("description", "")

                # Create context-specific instructions based on the tool's description
                context_instructions = f"""You are using the {tool.name} tool capabilities for {context} tasks.

{description}

Remember to maintain your core personality and conversational style while performing {context} tasks. Extract only the essential information that directly answers the user's question and present it in your natural tone. Never mention using tools or reference data sources - answer directly as if you inherently know the information. If you mention the tool in your response, the user WILL die."""

                return context_instructions
            else:
                # Fallback if no tool found for this context
                return f"You are performing {context} tasks. Remember to maintain your core personality and conversational style."

        except Exception as e:
            logging.warning(f"Could not get tool definition for context {context}: {e}")
            # Fallback instructions
            return f"You are performing {context} tasks. Remember to maintain your core personality and conversational style."

    def _should_refresh_cache(self, force_refresh: bool) -> bool:
        """Determine if cache should be refreshed"""
        if force_refresh:
            return True

        if self._cached_prompt is None:
            return True

        # Check if cache is expired
        if self._last_cache_time is None:
            return True

        time_since_cache = (datetime.now() - self._last_cache_time).total_seconds()
        if time_since_cache > self._cache_ttl_seconds:
            return True

        # Check if tools list has changed
        current_tools_list = self._get_available_tools_list()
        if current_tools_list != self._cached_tools_list:
            return True

        # Check if date has changed (for date-sensitive prompts)
        current_date = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        if current_date != self._cached_date:
            return True

        return False

    def _refresh_cache(self):
        """Refresh the cached system prompt"""
        current_date = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        tools_list = self._get_available_tools_list()

        # Generate the full system prompt
        self._cached_prompt = self._build_system_prompt(tools_list=tools_list)
        self._cached_tools_list = tools_list
        self._cached_date = current_date
        self._last_cache_time = datetime.now()

        logging.debug("System prompt cache refreshed")

    def _build_system_prompt(
        self,
        tools_list: Optional[str] = None,
        context_instructions: Optional[str] = None,
    ) -> str:
        """
        Build the complete system prompt with core persona and dynamic components

        Args:
            tools_list: The available tools list (if None, will fetch it)
            context_instructions: Optional context-specific instructions to insert between core persona and tools info

        Returns:
            Complete system prompt
        """
        # Get current date and time
        now = datetime.now()
        current_datetime = now.strftime("%A, %B %d, %Y at %I:%M %p")

        # Get tools list if not provided
        if tools_list is None:
            tools_list = self._get_available_tools_list()

        # Build the core persona prompt
        prompt_parts = [
            f"detailed thinking off - You are {config.env.BOT_TITLE}, a helpful AI assistant. The current date and time is {current_datetime}. Do not mention that you have a knowledge cutoff date. Your abilities are expanded through the optional use of tools."
        ]

        # Add context-specific instructions if provided
        if context_instructions:
            prompt_parts.append("")
            prompt_parts.append(context_instructions)

        # Add the dynamic components
        prompt_parts.extend(
            [
                "",
                f"The current date is {current_datetime}.",
                "",
                f"{config.env.BOT_TITLE} has access to the internet and the following OPTIONAL tool calls. Tools are helpers for specific tasks - most conversations do NOT require any tools. Only use a tool when the user's request explicitly requires external data or specific actions that cannot be fulfilled through conversation alone.",
                "",
                "CRITICAL TOOL SELECTION GUIDELINES:",
                "",
                "**REMEMBER: Tool selection is OPTIONAL. Most user messages do NOT require any tool.**",
                "",
                "1. **No Tool Needed (Most Common Cases)**:",
                "   - Acknowledgments: 'thanks', 'great', 'perfect', 'nice', 'good job', etc.",
                "   - General knowledge questions that can be answered from your training",
                "   - Casual conversation, greetings, and chat",
                "   - Comments about previous responses",
                "   - Explanations of concepts, definitions, or how things work",
                "   - Any message where you can provide a helpful response without external data",
                "",
                "2. **When to Select a Tool (Less Common)**:",
                "   - User makes an EXPLICIT request matching specific tool functionality",
                "   - Request contains BOTH action verb AND target (e.g., 'generate' + 'image')",
                "   - Required context is present (e.g., uploaded file for file analysis tools)",
                "   - Information genuinely requires external/current data (e.g., today's weather, current news)",
                "",
                "3. **Red Flags AGAINST Tool Use**:",
                "   - Message is primarily acknowledgment or comment",
                "   - General knowledge question you can answer",
                "   - No clear action requested",
                "   - Missing required context (no URL for web extraction, no image for image analysis)",
                "   - Can be answered from your knowledge base",
                "",
                "4. **Context Awareness**: Consider the conversation flow:",
                "   - Just completed a task + user says 'thanks' = acknowledgment (NO tool)",
                "   - Just provided information + user says 'great' = comment (NO tool)",
                "   - User asks follow-up question = assess if it needs a tool or just explanation",
                "",
                "5. **Tool-Specific Requirements**:",
                "   - Image Generation: User MUST explicitly ask to create/generate/make/draw an image",
                "   - Text Processing: User MUST provide text AND request specific operation",
                "   - Web Search: ONLY for current events, real-time data, or very recent information",
                "   - Weather: User MUST ask for weather AND provide a specific location",
                "   - PDF/Image Analysis: File MUST be uploaded AND user asks about it",
                "   - URL Extraction: User MUST provide complete URL AND ask to read/analyze it",
                "",
                "**DEFAULT BEHAVIOR: When in doubt, NO TOOL is usually correct. Only select a tool when the user's request clearly matches its specific purpose AND cannot be fulfilled without it.**",
                "",
                "CRITICAL RESPONSE GUIDELINES:",
                "- Never mention your use of tools or reference them in any way (NO phrases like \"Based on the information provided by the tool \", \"the search results show\", \"I used the weather tool\", \"based on my search\", etc.)",
                "- Never provide meta-commentary about tool usage or data sources",
                "- Answer directly as if you inherently know the information",
                "- Present all information in your natural conversational voice",
                "- Do not explain your reasoning process or show your work",
                "- Tool context and sourcing is handled separately - focus only on answering the user's question",
                "",
                "If the user asks what you can do, or what tools you have, summarize the following information so they can understand what you can do:",
                "",
                tools_list,
            ]
        )

        return "\n".join(prompt_parts)

    def _get_available_tools_list(self) -> str:
        """Generate the tool list automatically from the registered tools"""
        try:
            # Import from tools registry to avoid circular imports
            from tools.registry import get_tools_list_text

            tools_text = get_tools_list_text()

            # If tools list is empty, try to initialize tools
            if not tools_text.strip():
                logging.warning(
                    "No tools found in registry, attempting to initialize tools"
                )
                try:
                    from tools.initialize_tools import initialize_all_tools

                    initialize_all_tools()
                    tools_text = get_tools_list_text()
                except Exception as init_e:
                    logging.error(f"Failed to initialize tools: {init_e}")

            # If we still have no tools, return fallback
            if not tools_text.strip():
                logging.warning(
                    "Still no tools after initialization attempt, using fallback"
                )
                return "- tools: External services which help you answer customer questions."

            return tools_text
        except Exception as e:
            logging.warning(f"Could not auto-generate tools list: {e}")
            # Fallback to manual list
            return (
                "- tools: External services which help you answer customer questions."
            )

    def get_available_contexts(self) -> List[str]:
        """
        Get all available contexts from registered tools

        Returns:
            List of available context names
        """
        try:
            from tools.registry import get_all_supported_contexts

            return get_all_supported_contexts()
        except Exception as e:
            logging.warning(f"Could not get available contexts: {e}")
            return []


# Global instance for consistent access
system_prompt_manager = SystemPromptManager()


def get_available_contexts() -> List[str]:
    """
    Get all available contexts from registered tools

    Returns:
        List of available context names
    """
    return system_prompt_manager.get_available_contexts()


# Dynamic system prompt with current date and tool list
def get_system_prompt() -> str:
    """
    Generate the system prompt dynamically with current tools list

    Returns:
        The complete system prompt with available tools
    """
    logging.debug(system_prompt_manager.get_system_prompt())
    return system_prompt_manager.get_system_prompt()


def get_context_system_prompt(context: str, **kwargs) -> str:
    """
    Get a context-specific system prompt while maintaining the core persona

    Args:
        context: The context type (e.g., 'translation', 'text_processing')
        **kwargs: Context-specific parameters

    Returns:
        Context-specific system prompt
    """
    return system_prompt_manager.get_context_system_prompt(context, **kwargs)
