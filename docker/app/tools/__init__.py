# Import tool classes for registration
# Import helper functions for backward compatibility - only the definitions
from .assistant import AssistantResponse, AssistantTool, get_assistant_tool_definition
from .conversation_context import (
    ConversationContextResponse,
    ConversationContextTool,
    get_conversation_context_tool_definition,
)
from .extract import WebExtractResponse, WebExtractTool, get_web_extract_tool_definition
from .generalist import (
    GeneralistResponse,
    GeneralistTool,
    get_generalist_tool_definition,
)
from .image_analysis_tool import (
    ImageAnalysisResponse,
    ImageAnalysisTool,
    get_image_analysis_tool_definition,
)
from .image_gen import (
    ImageGenerationResponse,
    ImageGenerationTool,
    get_image_generation_tool_definition,
)
from .news import NewsTool
from .news import TavilyResponse as NewsResponse
from .news import get_news_tool_definition
from .pdf_summary import (
    PDFSummaryResponse,
    PDFSummaryTool,
    get_pdf_summary_tool_definition,
)
from .pdf_text_processor import (
    PDFTextProcessorResponse,
    PDFTextProcessorTool,
    get_pdf_text_processor_tool_definition,
)

# Import registry functions
from .registry import (
    execute_tool,
    get_all_tool_definitions,
    get_tool,
    get_tools_list_text,
    register_tool_class,
)
from .retriever import RetrievalResponse, RetrieverTool, get_retrieval_tool_definition
from .tavily import TavilyResponse, TavilyTool, get_tavily_tool_definition
from .weather import WeatherResponse, WeatherTool, get_weather_tool_definition

__all__ = [
    # Tool classes
    "AssistantTool",
    "ConversationContextTool",
    "WebExtractTool",
    "GeneralistTool",
    "ImageAnalysisTool",
    "ImageGenerationTool",
    "NewsTool",
    "PDFSummaryTool",
    "PDFTextProcessorTool",
    "RetrieverTool",
    "TavilyTool",
    "WeatherTool",
    # Response classes
    "AssistantResponse",
    "ConversationContextResponse",
    "WebExtractResponse",
    "GeneralistResponse",
    "ImageAnalysisResponse",
    "ImageGenerationResponse",
    "NewsResponse",
    "PDFSummaryResponse",
    "PDFTextProcessorResponse",
    "RetrievalResponse",
    "TavilyResponse",
    "WeatherResponse",
    # Helper functions - only definitions
    "get_assistant_tool_definition",
    "get_conversation_context_tool_definition",
    "get_web_extract_tool_definition",
    "get_generalist_tool_definition",
    "get_image_analysis_tool_definition",
    "get_image_generation_tool_definition",
    "get_news_tool_definition",
    "get_pdf_summary_tool_definition",
    "get_pdf_text_processor_tool_definition",
    "get_retrieval_tool_definition",
    "get_tavily_tool_definition",
    "get_weather_tool_definition",
    # Registry functions
    "get_all_tool_definitions",
    "get_tool",
    "get_tools_list_text",
    "register_tool_class",
    "execute_tool",
]
