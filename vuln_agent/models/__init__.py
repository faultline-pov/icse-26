from .openai import OpenAIGen, OpenAIEmbed
from .google import GoogleGen
from .claude import ClaudeGen
from dotenv import load_dotenv

load_dotenv()

class ModelException(Exception):
    pass


def get_model_from_name(name, logger):

    if name == "gpt4":
        return OpenAIGen(model="gpt-4-0125-preview", logger=logger)
    elif name == "gpt4o":
        return OpenAIGen(model="gpt-4o-2024-11-20", logger=logger)
    elif name == "gpt4o-mini":
        return OpenAIGen(model="gpt-4o-mini-2024-07-18", logger=logger)
    elif name == "gpt3":
        return OpenAIGen(model="gpt-3.5-turbo", logger=logger)
    elif name == "gemini":
        return GoogleGen(model="gemini-1.0-pro", logger=logger)
    elif name == "claude37":
        return ClaudeGen(model="claude-3-7-sonnet-20250219", logger=logger)
    elif name == "embedding":
        return OpenAIEmbed(model="text-embedding-3-large", logger=logger)
    else:
        raise NotImplementedError("Unknown model name")


__all__ = [
    "OpenAIGen",
    "GoogleGen",
    "ClaudeGen",
    "OpenAIEmbed",
    "ModelException",
    "get_model_from_name",
]
