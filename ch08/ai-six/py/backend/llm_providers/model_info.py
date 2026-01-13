"""
Model information for AI-6.

This module provides metadata about various AI models that can be used with AI-6,
such as their context window sizes. This information is used by the agent to
properly manage conversations, including when to summarize them to fit within
a model's context window.


Model information can be collected manually from the following sources:
https://ollama.com/models
https://platform.openai.com/docs/models
https://docs.anthropic.com/en/docs/about-claude/models
"""

# Dictionary mapping model IDs to their metadata
# Currently focused on context window sizes
model_info = {
    # OpenAI models
    "gpt-5": {
        "context_window_size": 400000,
        "provider": "openai",
        "description": "GPT-5 with 400K context (128k max output tokens)"
    },
    "gpt-4o": {
        "context_window_size": 128000,
        "provider": "openai",
        "description": "GPT-4o with 128K context (16k max output tokens)"
    },
    
    # Qwen models
    "qwen2.5-coder:32b": {
        "context_window_size": 128000,
        "provider": "ollama",
        "description": "Qwen 2.5 Coder 32B"
    },
    "qwen3:32b": {
        "context_window_size": 128000,
        "provider": "ollama",
        "description": "Qwen 3 32B"
    },
    
    # OpenAI OSS models
    "gpt-oss:20b": {
        "context_window_size": 128000,
        "provider": "ollama", 
        "description": "GPT-OSS 20B - Open source GPT model"
    },
    "gpt-oss:120b": {
        "context_window_size": 128000,
        "provider": "ollama", 
        "description": "GPT-OSS 120B - Open source GPT model"
    },
    
    # DeepSeek models
    "deepseek-r1:70b": {
        "context_window_size": 128000,
        "provider": "ollama",
        "description": "DeepSeek-R1 70B - Reasoning-focused model"
    },
    
    # Mistral models
    "devstral:24b": {
        "context_window_size": 128000,
        "provider": "ollama",
        "description": "Devstral 24B - Code-focused model"
    }
}


def get_context_window_size(model_id: str) -> int:
    if model_id in model_info:
        return model_info[model_id]["context_window_size"]
    raise KeyError(f"Model '{model_id}' not found in model_info dictionary")


def get_model_metadata(model_id: str) -> dict:
    if model_id in model_info:
        return model_info[model_id]
    raise KeyError(f"Model '{model_id}' not found in model_info dictionary")
