"""
backend/app/llm/gateway.py

LLM Gateway — provider abstraction with round-robin key rotation.

Primary:  Gemini (gemini-2.0-flash)
Fallback: OpenAI (gpt-4o-mini)

Usage:
    from app.llm.gateway import llm_gateway

    response = await llm_gateway.complete(
        messages      = [{"role": "user", "content": "Hello"}],
        system_prompt = "You are Einstein.",
        max_tokens    = 450,
    )

    quick = await llm_gateway.complete_fast("Rewrite this query: ...", max_tokens=40)
"""

import os
import asyncio
from typing import AsyncIterator

from dotenv import load_dotenv
import google.genai as genai
import google.genai.types as genai_types

from app.llm.round_robin import RoundRobinKeyManager, AllKeysExhausted

load_dotenv()


# ── Exceptions ────────────────────────────────────────────────────────────────

class RateLimitError(Exception):
    def __init__(self, message: str, key: str):
        super().__init__(message)
        self.key = key


class NoProvidersAvailable(Exception):
    pass


# ── Gateway ───────────────────────────────────────────────────────────────────

class LLMGateway:
    """
    Single interface for all LLM calls.
    Handles key rotation, provider fallback, and streaming.
    """

    def __init__(self):
        # Gemini key pool (up to 3 free-tier keys)
        gemini_keys = [
            os.getenv(f"GEMINI_KEY_{i}", "") for i in range(1, 4)
        ]
        # OpenAI fallback pool
        openai_keys = [
            os.getenv(f"OPENAI_KEY_{i}", "") for i in range(1, 3)
        ]
        # Groq pool
        groq_keys = [
            os.getenv(f"GROQ_KEY_{i}", "") for i in range(1, 4)
        ]

        self.key_managers = {
            "gemini": RoundRobinKeyManager(gemini_keys, "gemini"),
            "groq":   RoundRobinKeyManager(groq_keys, "groq"),
            "openai": RoundRobinKeyManager(openai_keys, "openai"),
        }

        # Preferred provider order
        active_provider = os.getenv("ACTIVE_PROVIDER", "gemini").lower()
        providers = ["gemini", "groq", "openai"]
        if active_provider in providers:
            providers.remove(active_provider)
            self.provider_order = [active_provider] + providers
        else:
            self.provider_order = ["gemini", "groq", "openai"]

    # ── Primary complete call ────────────────────────────────────────────────

    async def complete(
        self,
        messages     : list[dict],          # [{"role": "user"|"assistant", "content": str}]
        system_prompt: str,
        max_tokens   : int  = 450,
        stream       : bool = False,
        temperature  : float = 0.7,
    ) -> str:
        """
        Send a chat completion request.
        Tries each provider in order. Falls back on rate-limit.

        Returns the response text (str).
        Streaming is handled by complete_stream().
        """
        last_error = None

        for provider in self.provider_order:
            try:
                key = self.key_managers[provider].get_key()
            except AllKeysExhausted as e:
                print(f"[GATEWAY] {provider}: all keys exhausted — {e}")
                continue

            try:
                if provider == "gemini":
                    return await self._call_gemini(
                        key, messages, system_prompt, max_tokens, temperature
                    )
                elif provider == "groq":
                    return await self._call_groq(
                        key, messages, system_prompt, max_tokens, temperature
                    )
                elif provider == "openai":
                    return await self._call_openai(
                        key, messages, system_prompt, max_tokens, temperature
                    )

            except RateLimitError as e:
                self.key_managers[provider].mark_rate_limited(e.key)
                last_error = e
                continue  # try next key / provider

            except Exception as e:
                print(f"[GATEWAY] {provider} error: {e}")
                last_error = e
                continue

        raise NoProvidersAvailable(
            f"All LLM providers exhausted. Last error: {last_error}"
        )

    # ── Lightweight fast call (for query intelligence, faithfulness, etc.) ───

    async def complete_fast(
        self,
        prompt    : str,
        max_tokens: int   = 100,
    ) -> str:
        """
        Cheap, fast LLM call for internal utility tasks:
        query rewriting, HyDE generation, faithfulness scoring, etc.
        Uses temperature=0.1 for deterministic outputs.
        """
        return await self.complete(
            messages      = [{"role": "user", "content": prompt}],
            system_prompt = "Be concise and precise. Return only what is asked.",
            max_tokens    = max_tokens,
            temperature   = 0.1,
        )

    # ── Streaming call ───────────────────────────────────────────────────────

    async def complete_stream(
        self,
        messages     : list[dict],
        system_prompt: str,
        max_tokens   : int   = 450,
        temperature  : float = 0.7,
    ) -> AsyncIterator[str]:
        """
        Streaming version. Yields text chunks as they arrive.
        Used by WebSocket endpoint for typewriter effect.
        """
        for provider in self.provider_order:
            try:
                key = self.key_managers[provider].get_key()
            except AllKeysExhausted:
                continue

            try:
                if provider == "gemini":
                    async for chunk in self._stream_gemini(
                        key, messages, system_prompt, max_tokens, temperature
                    ):
                        yield chunk
                    return
                elif provider == "groq":
                    async for chunk in self._stream_groq(
                        key, messages, system_prompt, max_tokens, temperature
                    ):
                        yield chunk
                    return
                elif provider == "openai":
                    async for chunk in self._stream_openai(
                        key, messages, system_prompt, max_tokens, temperature
                    ):
                        yield chunk
                    return

            except RateLimitError as e:
                self.key_managers[provider].mark_rate_limited(e.key)
                continue
            except Exception as e:
                print(f"[GATEWAY] Stream error ({provider}): {e}")
                continue

        raise NoProvidersAvailable("All providers exhausted for streaming")

    # ── Gemini implementation ────────────────────────────────────────────────

    async def _call_gemini(
        self,
        key          : str,
        messages     : list[dict],
        system_prompt: str,
        max_tokens   : int,
        temperature  : float,
    ) -> str:
        client = genai.Client(api_key=key)

        # Build contents from messages
        contents = []
        for msg in messages:
            role    = "user" if msg["role"] == "user" else "model"
            contents.append(
                genai_types.Content(
                    role  = role,
                    parts = [genai_types.Part(text=msg["content"])]
                )
            )

        config = genai_types.GenerateContentConfig(
            system_instruction = system_prompt,
            max_output_tokens  = max_tokens,
            temperature        = temperature,
        )

        try:
            # Run in executor to avoid blocking the event loop
            loop     = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model    = "gemini-2.0-flash",
                    contents = contents,
                    config   = config,
                )
            )
            return response.text.strip()

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "rate" in error_str:
                raise RateLimitError(f"Gemini rate limit: {e}", key=key)
            raise

    async def _stream_gemini(
        self,
        key          : str,
        messages     : list[dict],
        system_prompt: str,
        max_tokens   : int,
        temperature  : float,
    ) -> AsyncIterator[str]:
        """Yield text tokens from Gemini streaming response."""
        client = genai.Client(api_key=key)

        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                genai_types.Content(
                    role  = role,
                    parts = [genai_types.Part(text=msg["content"])]
                )
            )

        config = genai_types.GenerateContentConfig(
            system_instruction = system_prompt,
            max_output_tokens  = max_tokens,
            temperature        = temperature,
        )

        try:
            loop = asyncio.get_event_loop()

            def _stream():
                return client.models.generate_content_stream(
                    model    = "gemini-2.0-flash",
                    contents = contents,
                    config   = config,
                )

            stream = await loop.run_in_executor(None, _stream)
            for chunk in stream:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "rate" in error_str:
                raise RateLimitError(f"Gemini stream rate limit: {e}", key=key)
            raise

    # ── OpenAI implementation ────────────────────────────────────────────────

    async def _call_openai(
        self,
        key          : str,
        messages     : list[dict],
        system_prompt: str,
        max_tokens   : int,
        temperature  : float,
    ) -> str:
        """OpenAI fallback using gpt-4o-mini."""
        try:
            import openai
        except ImportError:
            raise Exception("openai package not installed — add to requirements.txt")

        client = openai.AsyncOpenAI(api_key=key)

        full_messages = [{"role": "system", "content": system_prompt}] + messages

        try:
            response = await client.chat.completions.create(
                model       = "gpt-4o-mini",
                messages    = full_messages,
                max_tokens  = max_tokens,
                temperature = temperature,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str:
                raise RateLimitError(f"OpenAI rate limit: {e}", key=key)
            raise

    async def _stream_openai(
        self,
        key          : str,
        messages     : list[dict],
        system_prompt: str,
        max_tokens   : int,
        temperature  : float,
    ) -> AsyncIterator[str]:
        """OpenAI streaming fallback."""
        try:
            import openai
        except ImportError:
            raise Exception("openai package not installed — add to requirements.txt")

        client = openai.AsyncOpenAI(api_key=key)
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        try:
            stream = await client.chat.completions.create(
                model       = "gpt-4o-mini",
                messages    = full_messages,
                max_tokens  = max_tokens,
                temperature = temperature,
                stream      = True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str:
                raise RateLimitError(f"OpenAI stream rate limit: {e}", key=key)
            raise

    # ── Groq implementation ──────────────────────────────────────────────────

    async def _call_groq(
        self,
        key          : str,
        messages     : list[dict],
        system_prompt: str,
        max_tokens   : int,
        temperature  : float,
    ) -> str:
        """Groq completion via OpenAI-compatible endpoint."""
        try:
            import openai
        except ImportError:
            raise Exception("openai package not installed — add to requirements.txt")

        client = openai.AsyncOpenAI(
            api_key  = key,
            base_url = "https://api.groq.com/openai/v1"
        )
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        try:
            response = await client.chat.completions.create(
                model       = model,
                messages    = full_messages,
                max_tokens  = max_tokens,
                temperature = temperature,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str or "limit" in error_str:
                raise RateLimitError(f"Groq rate limit: {e}", key=key)
            raise

    async def _stream_groq(
        self,
        key          : str,
        messages     : list[dict],
        system_prompt: str,
        max_tokens   : int,
        temperature  : float,
    ) -> AsyncIterator[str]:
        """Groq streaming via OpenAI-compatible endpoint."""
        try:
            import openai
        except ImportError:
            raise Exception("openai package not installed — add to requirements.txt")

        client = openai.AsyncOpenAI(
            api_key  = key,
            base_url = "https://api.groq.com/openai/v1"
        )
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

        try:
            stream = await client.chat.completions.create(
                model       = model,
                messages    = full_messages,
                max_tokens  = max_tokens,
                temperature = temperature,
                stream      = True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str or "limit" in error_str:
                raise RateLimitError(f"Groq stream rate limit: {e}", key=key)
            raise

    # ── Key status ───────────────────────────────────────────────────────────

    def key_status(self) -> dict:
        """Return current key pool status for /admin/keys endpoint."""
        return {
            provider: mgr.status()
            for provider, mgr in self.key_managers.items()
        }


# ── Singleton instance ────────────────────────────────────────────────────────

llm_gateway = LLMGateway()
