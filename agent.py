import os
import sys
import json
import base64
from typing import List, Optional, Generator, Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from openai import OpenAI
from config import ANAKIN_API_KEY, ANAKIN_BASE_URL, DEFAULT_MODEL, MODEL_FALLBACKS

from tools.web_tool import search_web, scrape_url
from tools.science_tool import evaluate_math
from tools.code_tool import execute_python
import db

# Callable map for tool dispatch
TOOL_FUNCTIONS = {
    "search_web": search_web,
    "scrape_url": scrape_url,
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
            "description": "Scrape and extract clean text content from a web URL.",
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
    "You are Siluria, an Anakin.io powered autonomous, high-performance AI agent.\n"
    "You can:\n"
    "1. Search the live web (search_web) and read web pages (scrape_url).\n"
    "2. Evaluate mathematics and physics (evaluate_math).\n"
    "3. Execute arbitrary Python code (execute_python).\n\n"
    "Be concise, accurate, and proactive with tool use. "
    "You have full session history — maintain context across messages. "
    "Give thorough, detailed answers. When uncertain, search the web first."
)

MAX_TOOL_ROUNDS = 10


class SiluriaAgent:
    def __init__(self):
        self._client = None
        self.model_name = DEFAULT_MODEL

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            key = os.getenv("ANAKIN_API_KEY", ANAKIN_API_KEY)
            if not key:
                raise ValueError(
                    "ANAKIN_API_KEY is not set. Please add ANAKIN_API_KEY in your environment variables or Vercel Project Settings."
                )
            base_url = os.getenv("ANAKIN_BASE_URL", ANAKIN_BASE_URL)
            self._client = OpenAI(api_key=key, base_url=base_url)
        return self._client

    def _models(self) -> List[str]:
        seen, ordered = set(), []
        for m in [self.model_name] + MODEL_FALLBACKS:
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
                clean = re.sub(r'\n\n\*⚙ \[.*?\]\*\n\n', '', full_response)
                self.model_name = model
                db.add_message(session_id, "assistant", clean.strip())
                return

            except Exception as e:
                err = str(e)
                last_error = e
                if any(k in err for k in ("429", "insufficient_quota", "503", "404", "model_not_found")):
                    continue  # try next model fallback
                yield f"\n[Error: {err}]"
                return

        if last_error:
            yield f"\n[All models exhausted. Last error: {last_error}]"

    def _agentic_stream(
        self,
        model: str,
        messages: List[Dict[str, Any]],
    ) -> Generator[str, None, None]:
        """
        Agentic loop for one model: tool-call rounds followed by a streamed final answer.
        """
        for _round in range(MAX_TOOL_ROUNDS):
            # Check if model wants to call a tool
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS_SCHEMA,
                tool_choice="auto",
                stream=False
            )

            choice = response.choices[0]
            msg = choice.message

            if not msg.tool_calls:
                # No more tools requested. Stream final answer.
                stream = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stream=True
                )
                got_any = False
                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        got_any = True
                        yield delta.content

                if not got_any and msg.content:
                    yield msg.content
                return

            # Tool calls encountered
            tool_names = ", ".join([tc.function.name for tc in msg.tool_calls])
            yield f"\n\n*⚙ [{tool_names}]*\n\n"

            # Append assistant message with tool calls
            messages.append(msg.model_dump())

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
