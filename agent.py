import os
import json
from typing import List, Optional, Generator

from google import genai
from google.genai import types
from config import GEMINI_API_KEY, DEFAULT_MODEL, MODEL_FALLBACKS

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

AVAILABLE_TOOLS = list(TOOL_FUNCTIONS.values())

SYSTEM_INSTRUCTION = (
    "You are Siluria, a superior, autonomous, high-performance AI agent.\n"
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
    def client(self) -> genai.Client:
        if self._client is None:
            key = os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)
            if not key:
                raise ValueError("GEMINI_API_KEY is not set. Please add GEMINI_API_KEY in Vercel Project Settings > Environment Variables.")
            os.environ["GEMINI_API_KEY"] = key
            self._client = genai.Client(api_key=key)
        return self._client

    def _config_with_tools(self) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            tools=AVAILABLE_TOOLS,
        )

    def _config_plain(self) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
        )

    def _models(self) -> List[str]:
        seen, ordered = set(), []
        for m in [self.model_name] + MODEL_FALLBACKS:
            if m and m not in seen:
                seen.add(m)
                ordered.append(m)
        return ordered

    def _run_tool(self, fc) -> str:
        """Execute a Gemini function_call part and return the string result."""
        fn = TOOL_FUNCTIONS.get(fc.name)
        if not fn:
            return f"Unknown function: {fc.name}"
        try:
            args = dict(fc.args) if fc.args else {}
            result = fn(**args)
            if isinstance(result, (dict, list)):
                return json.dumps(result, default=str)[:10000]
            return str(result)[:10000]
        except Exception as e:
            return f"Tool error ({fc.name}): {e}"

    def stream_agent(
        self,
        user_query: str,
        session_id: str,
        file_paths: Optional[List[str]] = None,
        links: Optional[List[str]] = None,
    ) -> Generator[str, None, None]:
        """
        Drive the Gemini agentic loop with model fallback.
        Yields text chunks to stream to the client.
        """
        history = db.get_chat_history(session_id)

        # Build conversation contents from history
        contents: List[types.Content] = []
        for entry in history:
            role = "user" if entry["role"] == "user" else "model"
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=entry["content"])])
            )

        # Build current user message
        query_text = user_query
        if links:
            query_text += "\n\n**Attached URLs:**\n" + "\n".join(f"- {l}" for l in links)

        user_parts = [types.Part.from_text(text=query_text)]
        for path in file_paths or []:
            if os.path.isfile(path):
                try:
                    up = self.client.files.upload(file=path)
                    user_parts.append(
                        types.Part.from_uri(file_uri=up.uri, mime_type=up.mime_type)
                    )
                except Exception:
                    pass

        contents.append(types.Content(role="user", parts=user_parts))

        last_error = None
        for model in self._models():
            chunks_sent: List[str] = []
            try:
                for chunk_text in self._agentic_stream(model, list(contents)):
                    chunks_sent.append(chunk_text)
                    yield chunk_text

                # Persist full response
                full_response = "".join(chunks_sent)
                # Strip the tool-status markers from the saved text
                import re
                clean = re.sub(r'\n\n\*⚙ \[.*?\]\*\n\n', '', full_response)
                self.model_name = model
                db.add_message(session_id, "assistant", clean.strip())
                return

            except Exception as e:
                err = str(e)
                last_error = e
                if any(k in err for k in ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "404", "NOT_FOUND")):
                    continue  # try next model
                yield f"\n[Error: {err}]"
                return

        if last_error:
            yield f"\n[All models exhausted. Last error: {last_error}]"

    def _agentic_stream(
        self,
        model: str,
        contents: List[types.Content],
    ) -> Generator[str, None, None]:
        """
        Agentic loop for one model: tool-call rounds followed by a streamed final answer.
        Raises on API errors so caller can switch model.
        """
        for _round in range(MAX_TOOL_ROUNDS):
            # Blocking call to handle potential tool/function calls
            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config=self._config_with_tools(),
            )

            if not response.candidates:
                break

            candidate = response.candidates[0]
            parts = candidate.content.parts if candidate.content else []

            text_parts = [p.text for p in parts if getattr(p, "text", None)]
            fn_calls  = [p.function_call for p in parts if getattr(p, "function_call", None)]

            if not fn_calls:
                # No more tool calls — stream the final answer
                # Re-run as a stream (without tools) so tokens appear instantly
                final_contents = list(contents)
                stream = self.client.models.generate_content_stream(
                    model=model,
                    contents=final_contents,
                    config=self._config_plain(),
                )
                got_any = False
                for chunk in stream:
                    if chunk.text:
                        got_any = True
                        yield chunk.text
                # Fallback: if streaming gave nothing, yield blocking text
                if not got_any:
                    yield "".join(text_parts)
                return  # done

            # Tool calls → execute, feed back, loop
            tool_names = ", ".join(fc.name for fc in fn_calls)
            yield f"\n\n*⚙ [{tool_names}]*\n\n"

            # Append model's function-call turn
            contents.append(candidate.content)

            # Execute all tool calls
            result_parts = []
            for fc in fn_calls:
                result_str = self._run_tool(fc)
                result_parts.append(
                    types.Part.from_function_response(
                        name=fc.name,
                        response={"result": result_str},
                    )
                )

            # Feed results back as a user turn
            contents.append(types.Content(role="user", parts=result_parts))
            # Continue loop — model will now process the tool results
