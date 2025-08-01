"""
Text Processor Service

This service handles text processing operations like summarizing, proofreading,
rewriting, and critiquing text. Extracted from the monolithic AssistantTool.
"""

import asyncio
import logging
from enum import Enum
from typing import Dict, List, Optional

from models.chat_config import ChatConfig
from services.llm_client_service import llm_client_service
from utils.config import config as app_config

logger = logging.getLogger(__name__)


class TextTaskType(str, Enum):
    """Text processing task types"""

    SUMMARIZE = "summarize"
    PROOFREAD = "proofread"
    REWRITE = "rewrite"
    CRITIC = "critic"
    DEVELOP = "develop"


class TextProcessorService:
    """Service for text processing operations"""

    def __init__(self, config: ChatConfig, llm_type: str):
        """
        Initialize text processor service

        Args:
            config: Chat configuration
            llm_type: Type of LLM to use ("fast", "llm", "intelligent")
        """
        self.config = config
        self.llm_type = llm_type

    async def process_text(
        self,
        task_type: TextTaskType,
        text: str,
        instructions: Optional[str] = None,
        messages: Optional[List[Dict]] = None,
    ) -> Dict[str, any]:
        """
        Process text with specified task type

        Args:
            task_type: Type of processing task
            text: Text to process
            instructions: Optional additional instructions
            messages: Optional conversation messages for context

        Returns:
            Processing result dictionary
        """
        try:
            # Check if the text is too large for direct processing
            estimated_tokens = len(text) // 4  # Rough token estimation
            max_tokens = 100000  # Conservative limit to stay well under model limits

            if estimated_tokens > max_tokens:
                logger.warning(
                    f"Text too large ({estimated_tokens} estimated tokens), processing in chunks"
                )
                return await self._process_large_text_chunked(
                    task_type, text, instructions, messages
                )

            client = llm_client_service.get_async_client(self.llm_type)
            model_name = llm_client_service.get_model_name(self.llm_type)
            system_prompt = self._get_system_prompt(task_type, instructions)

            # Build messages
            if messages:
                final_messages = self._build_messages_with_context(
                    messages, system_prompt, text
                )
            else:
                final_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ]

            logger.debug(f"Processing text with {task_type} using {model_name}")

            response = await client.chat.completions.create(
                model=model_name,
                messages=final_messages,
                temperature=app_config.llm.DEFAULT_TEMPERATURE,
                top_p=app_config.llm.DEFAULT_TOP_P,
                frequency_penalty=app_config.llm.DEFAULT_FREQUENCY_PENALTY,
                presence_penalty=app_config.llm.DEFAULT_PRESENCE_PENALTY,
            )

            result = response.choices[0].message.content.strip()

            return {
                "success": True,
                "result": result,
                "task_type": task_type,
                "processing_notes": self._get_processing_notes(task_type, text, result),
            }

        except Exception as e:
            logger.error(f"Error processing text: {e}")
            return {"success": False, "error": str(e), "task_type": task_type}

    async def process_text_streaming(
        self,
        task_type: TextTaskType,
        text: str,
        instructions: Optional[str] = None,
        messages: Optional[List[Dict]] = None,
    ) -> Dict[str, any]:
        """
        Process text with streaming response from LLM

        Args:
            task_type: Type of processing to perform
            text: Text to process
            instructions: Additional instructions for processing
            messages: Optional conversation messages for context

        Returns:
            Dictionary with processing result
        """
        from utils.text_processing import StreamingThinkTagFilter

        try:
            # Check if the text is too large for direct processing
            estimated_tokens = len(text) // 4  # Rough token estimation
            max_tokens = 100000  # Conservative limit to stay well under model limits

            if estimated_tokens > max_tokens:
                logger.warning(
                    f"Text too large ({estimated_tokens} estimated tokens), processing in chunks"
                )
                return await self._process_large_text_chunked(
                    task_type, text, instructions, messages
                )

            client = llm_client_service.get_async_client(self.llm_type)
            model_name = llm_client_service.get_model_name(self.llm_type)
            system_prompt = self._get_system_prompt(task_type, instructions)

            # Build messages
            if messages:
                final_messages = self._build_messages_with_context(
                    messages, system_prompt, text
                )
            else:
                final_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ]

            logger.debug(
                f"Processing text with streaming {task_type} using {model_name}"
            )

            response = await client.chat.completions.create(
                model=model_name,
                messages=final_messages,
                temperature=app_config.llm.DEFAULT_TEMPERATURE,
                top_p=app_config.llm.DEFAULT_TOP_P,
                frequency_penalty=app_config.llm.DEFAULT_FREQUENCY_PENALTY,
                presence_penalty=app_config.llm.DEFAULT_PRESENCE_PENALTY,
                stream=True,  # Enable streaming
            )

            # Create think tag filter for streaming
            think_filter = StreamingThinkTagFilter()
            collected_result = ""

            # Process stream with think tag filtering
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    chunk_content = chunk.choices[0].delta.content
                    # Filter think tags from the chunk
                    filtered_content = think_filter.process_chunk(chunk_content)
                    if filtered_content:
                        collected_result += filtered_content

            # Get any remaining content from the filter
            final_content = think_filter.flush()
            if final_content:
                collected_result += final_content

            return {
                "success": True,
                "result": collected_result,
                "task_type": task_type,
                "processing_notes": self._get_processing_notes(
                    task_type, text, collected_result
                ),
            }

        except Exception as e:
            logger.error(f"Error processing text with streaming: {e}")
            return {"success": False, "error": str(e), "task_type": task_type}

    async def _process_large_text_chunked(
        self,
        task_type: TextTaskType,
        text: str,
        instructions: Optional[str] = None,
        messages: Optional[List[Dict]] = None,
    ) -> Dict[str, any]:
        """
        Process large text by splitting it into chunks and processing hierarchically

        Args:
            task_type: Type of processing task
            text: Text to process
            instructions: Optional additional instructions
            messages: Optional conversation messages for context

        Returns:
            Processing result dictionary
        """
        try:
            # Split text into chunks (approximately 80K characters each)
            chunk_size = 80000
            chunks = []

            for i in range(0, len(text), chunk_size):
                chunk = text[i : i + chunk_size]
                chunks.append(chunk)

            logger.info(f"Processing large text in {len(chunks)} chunks")

            # Process all chunks concurrently
            async def process_chunk_async(i: int, chunk: str):
                try:
                    chunk_instructions = (
                        f"{instructions} (Processing section {i+1} of {len(chunks)})"
                        if instructions
                        else f"Processing section {i+1} of {len(chunks)}"
                    )
                    chunk_result = await self._process_single_chunk(
                        task_type, chunk, chunk_instructions, messages
                    )
                    if chunk_result["success"]:
                        return chunk_result["result"]
                    else:
                        return f"Section {i+1} processing failed: {chunk_result.get('error', 'Unknown error')}"
                except Exception as e:
                    logger.error(f"Error processing chunk {i+1}: {e}")
                    return f"Section {i+1} processing failed due to error: {str(e)}"

            # Run all chunk processing tasks concurrently
            chunk_results = await asyncio.gather(
                *[process_chunk_async(i, chunk) for i, chunk in enumerate(chunks)],
                return_exceptions=True,
            )

            # Handle any exceptions in results
            processed_results = []
            for i, result in enumerate(chunk_results):
                if isinstance(result, Exception):
                    logger.error(f"Chunk {i+1} failed with exception: {result}")
                    processed_results.append(
                        f"Section {i+1} processing failed due to error: {str(result)}"
                    )
                else:
                    processed_results.append(result)

            chunk_results = processed_results

            if not chunk_results:
                return {
                    "success": False,
                    "error": "No content could be processed from the text.",
                }

            # Combine chunk results based on task type
            if task_type == TextTaskType.SUMMARIZE:
                return await self._combine_summaries(chunk_results, instructions)
            elif task_type == TextTaskType.TRANSLATE:
                return await self._combine_translations(chunk_results)
            else:
                return await self._combine_general_results(
                    chunk_results, task_type, instructions
                )

        except Exception as e:
            logger.error(f"Error in chunked text processing: {e}")
            return {"success": False, "error": str(e), "task_type": task_type}

    async def _process_single_chunk(
        self,
        task_type: TextTaskType,
        chunk_text: str,
        instructions: Optional[str],
        messages: Optional[List[Dict]],
    ) -> Dict[str, any]:
        """
        Process a single chunk of text

        Args:
            task_type: Type of processing task
            chunk_text: The text chunk to process
            instructions: Processing instructions
            messages: Optional conversation messages for context

        Returns:
            Processing result dictionary
        """
        try:
            client = llm_client_service.get_async_client(self.llm_type)
            model_name = llm_client_service.get_model_name(self.llm_type)
            system_prompt = self._get_system_prompt(task_type, instructions)

            # Build messages
            if messages:
                final_messages = self._build_messages_with_context(
                    messages, system_prompt, chunk_text
                )
            else:
                final_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": chunk_text},
                ]

            response = await client.chat.completions.create(
                model=model_name,
                messages=final_messages,
                temperature=app_config.llm.DEFAULT_TEMPERATURE,
                top_p=app_config.llm.DEFAULT_TOP_P,
                frequency_penalty=app_config.llm.DEFAULT_FREQUENCY_PENALTY,
                presence_penalty=app_config.llm.DEFAULT_PRESENCE_PENALTY,
            )

            result = response.choices[0].message.content.strip()

            return {
                "success": True,
                "result": result,
                "task_type": task_type,
                "processing_notes": f"Chunk processing completed for {task_type}",
            }

        except Exception as e:
            logger.error(f"Error processing chunk: {e}")
            return {"success": False, "error": str(e), "task_type": task_type}

    async def _combine_summaries(
        self, chunk_results: List[str], instructions: Optional[str]
    ) -> Dict[str, any]:
        """Combine multiple summaries into a final summary"""
        try:
            combined_text = "\n\n---\n\n".join(chunk_results)

            synthesis_instructions = (
                f"Create an executive summary based on these section summaries. "
                f"Combine the information into a cohesive whole. {instructions or ''}"
            )

            return await self._process_single_chunk(
                TextTaskType.SUMMARIZE, combined_text, synthesis_instructions, None
            )
        except Exception as e:
            logger.error(f"Error combining summaries: {e}")
            return {
                "success": False,
                "error": str(e),
                "task_type": TextTaskType.SUMMARIZE,
            }

    async def _combine_translations(self, chunk_results: List[str]) -> Dict[str, any]:
        """Combine multiple translations into a final translation"""
        try:
            # For translations, just concatenate the results
            combined_result = "\n\n".join(chunk_results)
            return {
                "success": True,
                "result": combined_result,
                "task_type": TextTaskType.TRANSLATE,
                "processing_notes": "Translation completed in chunks and combined",
            }
        except Exception as e:
            logger.error(f"Error combining translations: {e}")
            return {
                "success": False,
                "error": str(e),
                "task_type": TextTaskType.TRANSLATE,
            }

    async def _combine_general_results(
        self,
        chunk_results: List[str],
        task_type: TextTaskType,
        instructions: Optional[str],
    ) -> Dict[str, any]:
        """Combine results for general text processing tasks"""
        try:
            combined_text = "\n\n---\n\n".join(chunk_results)

            synthesis_instructions = (
                f"Process the combined content from all sections. "
                f"Ensure consistency and coherence across the entire document. {instructions or ''}"
            )

            return await self._process_single_chunk(
                task_type, combined_text, synthesis_instructions, None
            )
        except Exception as e:
            logger.error(f"Error combining general results: {e}")
            return {"success": False, "error": str(e), "task_type": task_type}

    def _get_system_prompt(
        self, task_type: TextTaskType, instructions: Optional[str] = None
    ) -> str:
        """Get the appropriate system prompt for text processing tasks"""
        from utils.system_prompt import get_context_system_prompt

        # Use the new context-aware system prompt
        return get_context_system_prompt(
            context='text_processing',
            task_type=task_type.value,
            instructions=instructions,
        )

    def _build_messages_with_context(
        self, messages: List[Dict], system_prompt: str, text: str
    ) -> List[Dict]:
        """Build messages with proper context injection"""

        # Filter out existing system messages with task prompts
        filtered_messages = [
            msg
            for msg in messages
            if msg.get("role") != "system"
            or not any(
                task.value in msg.get("content", "").lower() for task in TextTaskType
            )
        ]

        # Check for injected context in text
        if "--- Additional Context ---" in text:
            parts = text.split("--- Additional Context ---")
            if len(parts) == 2:
                parts[0].strip()
                context = parts[1].strip()

                return [
                    {"role": "system", "content": system_prompt},
                    {"role": "system", "content": f"Additional context:\n\n{context}"},
                ] + filtered_messages

        return [{"role": "system", "content": system_prompt}] + filtered_messages

    def _get_processing_notes(
        self, task_type: TextTaskType, original: str, result: str
    ) -> str:
        """Generate processing notes for the task"""

        if task_type == TextTaskType.SUMMARIZE:
            return f"Original: {len(original.split())} words, Summary: {len(result.split())} words"
        elif task_type == TextTaskType.PROOFREAD:
            return "Proofreading completed with suggestions for improvement"
        elif task_type == TextTaskType.REWRITE:
            return "Text has been rewritten for improved clarity and flow"
        elif task_type == TextTaskType.CRITIC:
            return "Critical analysis and feedback provided"
        elif task_type == TextTaskType.DEVELOP:
            return "Code is ready for review"
