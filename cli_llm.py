"""Models reached through logged-in command-line tools on the owner's own machine.

`codex/<model>` runs `codex exec` and `claude/<model>` runs `claude -p`. Both can do
real web search. Neither needs a key in this repository, and neither works on
GitHub-hosted runners, so these models are for the local runner only.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

from forecasting_tools import GeneralLlm

_SYSTEM = "You are a careful research and forecasting assistant. Answer in English."
_TIMEOUT_SECONDS = 600
_SLOTS = asyncio.Semaphore(int(os.getenv("CLI_LLM_CONCURRENCY", "4")))


class CliLlm(GeneralLlm):
    def __init__(self, model: str, *, search: bool = False, effort: str = "high"):
        if not model.startswith(("codex/", "claude/")):
            raise ValueError(f"CliLlm needs a codex/ or claude/ model, not {model}.")
        super().__init__(model=model, allowed_tries=1)
        self._tool, self._cli_model = model.split("/", 1)
        self._search = search
        self._effort = effort
        self.request_count = 0

    async def invoke(self, prompt, system_prompt: str | None = None) -> str:
        if not isinstance(prompt, str):
            prompt = "\n\n".join(m.get("content", "") for m in self.model_input_to_message(prompt))
        if system_prompt:
            prompt = f"{system_prompt}\n\n{prompt}"
        run = self._run_codex if self._tool == "codex" else self._run_claude
        async with _SLOTS:
            answer = await run(prompt)
        self.request_count += 1
        if not answer.strip():
            raise RuntimeError(f"{self.model} returned no answer text.")
        return answer.strip()

    async def _run_claude(self, prompt: str) -> str:
        tools = "WebSearch,WebFetch" if self._search else ""
        command = ["claude", "-p", "--model", self._cli_model, "--effort", self._effort,
                   "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                   "--no-session-persistence", "--system-prompt", _SYSTEM, "--tools", tools,
                   "--allowedTools", tools, "--output-format", "json", "--max-budget-usd", "3"]
        with tempfile.TemporaryDirectory() as folder:
            output = await _communicate(command, prompt, folder)
        result = json.loads(output)
        if result.get("is_error") or result.get("subtype") != "success":
            raise RuntimeError(f"{self.model} failed: {result.get('subtype')}")
        return str(result.get("result", ""))

    async def _run_codex(self, prompt: str) -> str:
        with tempfile.TemporaryDirectory() as folder:
            answer_file = Path(folder) / "answer.txt"
            command = ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-m", self._cli_model,
                       "-c", f"model_reasoning_effort={self._effort}", "-s", "read-only",
                       "-C", folder, "-o", str(answer_file)]
            if self._search:
                command += ["-c", 'web_search="live"']
            await _communicate(command + ["-"], prompt, folder)
            return answer_file.read_text(encoding="utf-8") if answer_file.exists() else ""

    def to_dict(self) -> dict:
        return {"model": self.model, "provider": "local-cli", "research": self._search}

    def usage_summary(self) -> dict:
        return {**self.to_dict(), "requests": self.request_count, "cost_usd": None}


async def _communicate(command: list[str], prompt: str, folder: str) -> str:
    process = await asyncio.create_subprocess_exec(
        *command, cwd=folder, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(prompt.encode()), _TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise RuntimeError(f"{command[0]} timed out after {_TIMEOUT_SECONDS}s.") from None
    if process.returncode != 0:
        raise RuntimeError(f"{command[0]} exited with {process.returncode}: {stderr.decode()[-300:]}")
    return stdout.decode()


class RotatingLlm(GeneralLlm):
    """Hand each forecast to the next model, so one question gets several independent minds."""

    def __init__(self, members: list[GeneralLlm]):
        super().__init__(model="+".join(m.model for m in members), allowed_tries=1)
        self.members = members
        self._next = 0

    async def invoke(self, prompt, system_prompt: str | None = None) -> str:
        start = self._next
        self._next += 1
        failure: Exception | None = None
        for step in range(len(self.members)):
            member = self.members[(start + step) % len(self.members)]
            try:
                answer = await member.invoke(prompt, system_prompt)
                return f"(Forecaster model: {member.model})\n{answer}"
            except Exception as error:  # A failed model must not cost the question.
                print(f"{member.model} failed: {type(error).__name__}; trying the next model.")
                failure = error
        raise RuntimeError("Every forecasting model failed.") from failure

    def to_dict(self) -> dict:
        return {"model": self.model, "provider": "rotation"}

    def usage_summary(self) -> dict:
        return {"model": self.model, "members": [m.usage_summary() for m in self.members
                                                 if hasattr(m, "usage_summary")]}
