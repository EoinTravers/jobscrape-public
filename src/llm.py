import asyncio
from textwrap import dedent

from openai import OpenAI, AsyncOpenAI
from asynciolimiter import Limiter
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional, TypeVar, overload
from tqdm.asyncio import tqdm_asyncio
import tiktoken

"""
This is an interface for working with the OpenAI API.
I'll eventually tidy this up and post it to pypy.
"""

ResponseFormatType = TypeVar("ResponseFormatType", bound=BaseModel)


class OpenAIClient:
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        embedding_model: str = "text-embedding-3-small",
        embedding_dim: int = 1024,
        max_embedding_tokens: int = 8192,  # Only change this for testing
        reqs_per_minute: int = 60,
    ) -> None:
        load_dotenv()
        self.client = OpenAI()
        self.model = model
        self.embedding_model = embedding_model
        self.embedding_dim = embedding_dim
        self.max_embedding_tokens = max_embedding_tokens
        self.async_client = AsyncOpenAI()
        self.rate_limiter = Limiter(reqs_per_minute / 60)

    def _count_tokens(self, text: str) -> int:
        encoding = tiktoken.encoding_for_model(self.model)
        return len(encoding.encode(text))

    def _chat(self, messages: list[dict], **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore
            **kwargs,
        )
        if response.choices[0].message.content is None:
            raise ValueError("No content in response")
        return response.choices[0].message.content

    async def _chat_async(self, messages: list[dict], **kwargs) -> str:
        response = await self.async_client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore
            **kwargs,
        )
        if response.choices[0].message.content is None:
            raise ValueError("No content in response")
        return response.choices[0].message.content

    def _structured_chat(
        self, messages: list[dict], response_format: type[ResponseFormatType], **kwargs
    ) -> ResponseFormatType:
        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,  # type: ignore
            response_format=response_format,  # type: ignore
            **kwargs,
        )
        if response.choices[0].message.parsed is None:
            raise ValueError("No parsed response")
        return response.choices[0].message.parsed

    async def _structured_chat_async(
        self, messages: list[dict], response_format: type[ResponseFormatType], **kwargs
    ) -> ResponseFormatType:
        response = await self.async_client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,  # type: ignore
            response_format=response_format,  # type: ignore
            **kwargs,
        )
        if response.choices[0].message.parsed is None:
            raise ValueError("No parsed response")
        return response.choices[0].message.parsed

    def chat(
        self,
        messages: list[dict],
        response_format: Optional[type[ResponseFormatType]] = None,
        **kwargs,
    ) -> str | ResponseFormatType:
        if response_format is None:
            return self._chat(messages, **kwargs)
        else:
            return self._structured_chat(messages, response_format, **kwargs)

    async def chat_async(
        self,
        messages: list[dict],
        response_format: Optional[type[ResponseFormatType]] = None,
        **kwargs,
    ) -> str | ResponseFormatType:
        await self.rate_limiter.wait()
        if response_format is None:
            return await self._chat_async(messages, **kwargs)
        else:
            return await self._structured_chat_async(
                messages, response_format, **kwargs
            )

    # Tell mypy that llm() returns str if response_format is None, ResponseFormatType otherwise
    @overload
    def llm(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: None = None,
        **kwargs,
    ) -> str: ...

    @overload
    def llm(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: type[ResponseFormatType],
        **kwargs,
    ) -> ResponseFormatType: ...

    def llm(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: type[ResponseFormatType] | None = None,
        **kwargs,
    ) -> str | ResponseFormatType:
        return self.chat(
            [
                {"role": "system", "content": clean_string(system_prompt)},
                {"role": "user", "content": clean_string(user_prompt)},
            ],
            response_format=response_format,
            **kwargs,
        )


    @overload
    async def llm_async(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: None = None,
        **kwargs,
    ) -> str: ...

    @overload
    async def llm_async(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: type[ResponseFormatType],
        **kwargs,
    ) -> ResponseFormatType: ...

    async def llm_async(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[type[ResponseFormatType]] = None,
        **kwargs,
    ) -> str | ResponseFormatType:
        return await self.chat_async(
            [
                {"role": "system", "content": clean_string(system_prompt)},
                {"role": "user", "content": clean_string(user_prompt)},
            ],
            response_format=response_format,
            **kwargs,
        )

    @overload
    async def llm_batch(
        self,
        system_prompt: str | list[str],
        user_prompt: str | list[str],
        response_format: None,
        progress_bar: bool,
        **kwargs,
    ) -> list[str]: ...

    @overload
    async def llm_batch(
        self,
        system_prompt: str | list[str],
        user_prompt: str | list[str],
        response_format: type[ResponseFormatType],
        progress_bar: bool,
        **kwargs,
    ) -> list[ResponseFormatType]: ...

    async def llm_batch(
        self,
        system_prompt: str | list[str],
        user_prompt: str | list[str],
        response_format: Optional[type[ResponseFormatType]] = None,
        progress_bar: bool = False,
        **kwargs,
    ) -> list[str] | list[ResponseFormatType]:
        if isinstance(system_prompt, str) and isinstance(user_prompt, str):
            raise TypeError("Not a batch request")
        if isinstance(system_prompt, str):
            system_prompt = [system_prompt] * len(user_prompt)
        elif isinstance(user_prompt, str):
            user_prompt = [user_prompt] * len(system_prompt)
        elif len(system_prompt) != len(user_prompt):
            raise ValueError(
                "system_prompt and user_prompt lists must have same length"
            )

        tasks = [
            self.llm_async(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format=response_format,
                **kwargs,
            )
            for system_prompt, user_prompt in zip(system_prompt, user_prompt)
        ]
        if progress_bar:
            return await tqdm_asyncio.gather(*tasks)
        else:
            return await asyncio.gather(*tasks)

    def _embed(self, text: list[str], **kwargs) -> list[list[float]]:
        response = self.client.embeddings.create(
            model=self.embedding_model,
            dimensions=self.embedding_dim,
            input=text,
            **kwargs,
        ).data
        result = [d.embedding for d in response]
        return result

    def embed(self, text: str | list[str], **kwargs) -> list[list[float]]:
        if isinstance(text, str):
            return self._embed([text], **kwargs)
        else:
            # Check if can go in one request
            token_counts = [self._count_tokens(t) for t in text]
            if sum(token_counts) <= self.max_embedding_tokens:
                return self._embed(text, **kwargs)
            else:
                # TODO: Use async version
                # Split into batches of 8192 tokens
                batches: list[list[str]] = []
                current_token_count: int = 0
                current_batch: list[str] = []
                for t in text:
                    n = self._count_tokens(t)
                    if current_token_count + n > self.max_embedding_tokens:
                        batches.append(current_batch)
                        current_batch = []
                        current_token_count = 0
                    current_batch.append(t)
                    current_token_count += n
                batches.append(current_batch)
                results = [
                    self._embed(batch, **kwargs) for batch in batches
                ]  # list[list[list[float]]
                return [item for sublist in results for item in sublist]


def clean_string(s: str) -> str:
    for i in range(2):
        s = s.strip()
        s = dedent(s)
    return s


