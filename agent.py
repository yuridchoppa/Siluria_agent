import os
import sys
import json
import base64
from typing import List, Optional, Generator, Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from openai import OpenAI
from config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    DEFAULT_MODEL,
    MODEL_FALLBACKS,
    ACTIVE_PROVIDER,
    ANAKIN_API_KEY,
    GEMINI_API_KEY,
)

from tools.web_tool import search_web, scrape_url, anakin_scrape
from tools.science_tool import evaluate_math
from tools.code_tool import execute_python
import db

# Callable map for tool dispatch
TOOL_FUNCTIONS = {
    "search_web": search_web,
    "scrape_url": scrape_url,
    "anakin_scrape": anakin_scrape,
    "evaluate_math": evaluate_math,
    "execute_python": execute_python,
}

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the live web using DuckDuckGo and return top search results.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up on the web."
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results to return (default: 5).",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "scrape_url",
            "description": "Scrape and extract clean LLM-ready markdown from a web URL using the AnakinScraper engine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to scrape text from."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "anakin_scrape",
            "description": "Scrape and extract clean LLM-ready markdown from any web page using AnakinScraper (https://github.com/Anakin-Inc/anakin). Features multi-stage fallback (HTTP -> Anti-detect Browser -> Anakin.io Hosted API).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The web URL to scrape with AnakinScraper."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "evaluate_math",
            "description": "Evaluate a mathematical expression, calculus, or physics formula using SymPy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "The mathematical expression to evaluate (e.g., 'sin(pi/2) + integrate(x**2, x)')."
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_python",
            "description": "Execute arbitrary Python code in the sandbox/workspace for calculations, data analysis, or scripting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The Python code to execute."
                    }
                },
                "required": ["code"]
            }
        }
    }
]

SYSTEM_INSTRUCTION = (
    "You are Siluria (AnakinForge), an autonomous, high-performance AI agent.\n"
    "You are integrated with AnakinScraper (https://github.com/Anakin-Inc/anakin) and powered by Anakin.io / Google Gemini.\n"
    "Your capabilities include:\n"
    "1. High-performance web scraping and LLM-ready markdown extraction via AnakinScraper (anakin_scrape, scrape_url).\n"
    "2. Real-time web search (search_web).\n"
    "3. Symbolic and numeric mathematical computation (evaluate_math).\n"
    "4. Python execution sandbox for scripting and data analysis (execute_python).\n\n"
    "Be concise, insightful, and proactive with tools. Maintain session context across turns. "
    "When researching or answering questions about websites or current events, use AnakinScraper and web search proactively."
)

MAX_TOOL_ROUNDS = 3


class SiluriaAgent:
    def __init__(self):
        self._client = None
        self.model_name = DEFAULT_MODEL

    @property
    def client(self) -> OpenAI:
        key = (
            os.getenv("LLM_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("ANAKIN_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or LLM_API_KEY
            or GEMINI_API_KEY
            or ANAKIN_API_KEY
        )
        base_url = (
            os.getenv("LLM_BASE_URL")
            or LLM_BASE_URL
        )
        if not key:
            raise ValueError(
                "No LLM API Key configured. Please set GEMINI_API_KEY or ANAKIN_API_KEY in your .env or Vercel Environment Variables."
            )
        if self._client is None or getattr(self, "_cached_key", None) != key:
            self._cached_key = key
            self._client = OpenAI(api_key=key, base_url=base_url if base_url else None)
        return self._client

    def _models(self) -> List[str]:
        default = (os.getenv("DEFAULT_MODEL") or self.model_name or DEFAULT_MODEL).strip()
        fallbacks_str = os.getenv("MODEL_FALLBACKS")
        if fallbacks_str:
            fallbacks = [m.strip() for m in fallbacks_str.split(",") if m.strip()]
        else:
            fallbacks = MODEL_FALLBACKS

        seen, ordered = set(), []
        for m in [default] + fallbacks:
            if m and m not in seen:
                seen.add(m)
                ordered.append(m)
        return ordered

    def _run_tool(self, name: str, args_json: str) -> str:
        """Execute a tool function by name and arguments JSON, returning the string result."""
        fn = TOOL_FUNCTIONS.get(name)
        if not fn:
            return f"Unknown function: {name}"
        try:
            args = json.loads(args_json) if args_json else {}
            result = fn(**args)
            if isinstance(result, (dict, list)):
                return json.dumps(result, default=str)[:10000]
            return str(result)[:10000]
        except Exception as e:
            return f"Tool error ({name}): {e}"

    def stream_agent(
        self,
        user_query: str,
        session_id: str,
        file_paths: Optional[List[str]] = None,
        links: Optional[List[str]] = None,
    ) -> Generator[str, None, None]:
        """
        Drive the Anakin.io agentic loop with model fallback.
        Yields text chunks to stream to the client.
        """
        # Immediate invisible chunk to establish HTTP 200 and satisfy serverless connection timeouts
        yield "\u200b"

        history = db.get_chat_history(session_id)

        # Build conversation messages from history
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_INSTRUCTION}
        ]

        for entry in history:
            role = "user" if entry["role"] == "user" else "assistant"
            messages.append({"role": role, "content": entry["content"]})

        # Build current user message
        query_text = user_query
        if links:
            query_text += "\n\n**Attached URLs:**\n" + "\n".join(f"- {l}" for l in links)

        # Handle multimodal / image files if attached
        user_content: Any = query_text
        image_parts = []
        for path in file_paths or []:
            if os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                    try:
                        with open(path, "rb") as img_f:
                            b64_data = base64.b64encode(img_f.read()).decode("utf-8")
                            mime = f"image/{ext.replace('.', '')}"
                            if ext == ".jpg":
                                mime = "image/jpeg"
                            image_parts.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{b64_data}"}
                            })
                    except Exception:
                        pass

        if image_parts:
            user_content = [{"type": "text", "text": query_text}] + image_parts

        messages.append({"role": "user", "content": user_content})

        last_error = None
        for model in self._models():
            chunks_sent: List[str] = []
            try:
                for chunk_text in self._agentic_stream(model, list(messages)):
                    chunks_sent.append(chunk_text)
                    yield chunk_text

                # Persist full response
                full_response = "".join(chunks_sent)
                import re
                clean = re.sub(r'\n\n\*(?:⚙|\[Tool:|⚜ Communing with) .*?\*\n\n|\n\n\*⚙ \[.*?\]\*\n\n', '', full_response)
                self.model_name = model
                db.add_message(session_id, "assistant", clean.strip())
                return

            except Exception as e:
                err = str(e)
                last_error = e
                print(f"Model {model} failed: {err}")
                continue  # try next model fallback

        if last_error:
            yield f"\n\n⚠️ **Communication Error:** All available models failed to respond.\n*Last error:* `{last_error}`\n\nPlease verify your API key (`GEMINI_API_KEY` or `ANAKIN_API_KEY`) in your Vercel Environment Variables."

    def _agentic_stream(
        self,
        model: str,
        messages: List[Dict[str, Any]],
    ) -> Generator[str, None, None]:
        """
        Agentic loop for one model: tool-call rounds followed by a streamed final answer.
        """
        for _round in range(MAX_TOOL_ROUNDS):
            # On the final tool round, force synthesis without requesting further tools
            is_final_round = (_round == MAX_TOOL_ROUNDS - 1)
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=TOOLS_SCHEMA if not is_final_round else None,
                    tool_choice="none" if is_final_round else "auto",
                    stream=False
                )
            except Exception as e:
                # If function calling is not supported by the model/endpoint, fall back to plain completion
                err_str = str(e).lower()
                if any(k in err_str for k in ("tools", "function", "unrecognized", "schema", "argument")):
                    stream = self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        stream=True
                    )
                    for chunk in stream:
                        delta = chunk.choices[0].delta if chunk.choices else None
                        if delta and delta.content:
                            yield delta.content
                    return
                raise e

            choice = response.choices[0]
            msg = choice.message

            if not msg.tool_calls:
                # The model produced the final answer
                if msg.content:
                    yield msg.content
                else:
                    stream = self.client.chat.completions.create(
                        model=model,
                        messages=messages,
                        stream=True
                    )
                    for chunk in stream:
                        delta = chunk.choices[0].delta if chunk.choices else None
                        if delta and delta.content:
                            yield delta.content
                return

            # Tool calls encountered
            tool_names = ", ".join([tc.function.name for tc in msg.tool_calls])
            yield f"\n\n*⚜ Communing with {tool_names}...*\n\n"

            # Build clean assistant message preserving tool calls
            asst_dict: Dict[str, Any] = {
                "role": "assistant",
                "tool_calls": []
            }
            if msg.content:
                asst_dict["content"] = msg.content
            else:
                asst_dict["content"] = None

            for tc in msg.tool_calls:
                tc_dict = {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                extra = getattr(tc, "extra_content", None)
                if extra:
                    tc_dict["extra_content"] = extra
                asst_dict["tool_calls"].append(tc_dict)

            messages.append(asst_dict)

            # Execute tool calls and append results
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                fn_args = tc.function.arguments
                result_str = self._run_tool(fn_name, fn_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": fn_name,
                    "content": result_str
                })

        # If tool rounds completed without generating final text, synthesize the final answer
        try:
            stream = self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True
            )
            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
        except Exception as synth_err:
            print(f"Final synthesis error on {model}: {synth_err}")
            raise synth_err
