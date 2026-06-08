"""Interactive CLI for the RAG chatbot.

Usage::

    python -m chatbot
    python -m chatbot --collection akirs_businesses
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import textwrap
import uuid

from chatbot.config import settings
from chatbot.ingestion.ingestor import Ingestor
from chatbot.rag.pipeline import RAGPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("chatbot.cli")


# ANSI escape codes for terminal colors.
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_DIM = "\033[2m"
_RESET = "\033[0m"
_BOLD = "\033[1m"

HELP_TEXT = f"""
{_BOLD}Commands:{_RESET}
  {_CYAN}/collection <name>{_RESET}   Switch to a different collection.
  {_CYAN}/collections{_RESET}          List available collections.
  {_CYAN}/ingest <text>{_RESET}         Ingest raw text into the current collection.
  {_CYAN}/ingest-file <path>{_RESET}    Ingest a text file into the current collection.
  {_CYAN}/ingest-scraper{_RESET}        Pull data from the scraper DB.
  {_CYAN}/delete <name>{_RESET}         Delete a collection.
  {_CYAN}/health{_RESET}                Show health status (LLM + vector store).
  {_CYAN}/help{_RESET}                  Show this help.
  {_CYAN}/quit{_RESET} or {_CYAN}/exit{_RESET}      Exit the chatbot.

Just type a question to query the current collection.
"""

WELCOME = f"""
{_BOLD}{_CYAN}╔══════════════════════════════════════════════════╗
║     Akirs RAG Chatbot — Phi-4-mini via Ollama     ║
╚══════════════════════════════════════════════════╝{_RESET}
Type {_CYAN}/help{_RESET} for commands, or just ask a question.

{_DIM}Current collection:{_RESET} {{collection}}
"""


class ChatbotCLI:
    """Interactive command-line interface for the RAG chatbot."""

    def __init__(self, collection: str = "default") -> None:
        self.collection = collection
        self._pipeline: RAGPipeline | None = None
        self._ingestor: Ingestor | None = None

    @property
    def pipeline(self) -> RAGPipeline:
        if self._pipeline is None:
            self._pipeline = RAGPipeline()
        return self._pipeline

    @property
    def ingestor(self) -> Ingestor:
        if self._ingestor is None:
            self._ingestor = Ingestor()
        return self._ingestor

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start the interactive REPL."""
        print(WELCOME.format(collection=f"{_GREEN}{self.collection}{_RESET}"))

        while True:
            try:
                raw = input(f"{_GREEN}{self.collection}{_RESET}> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not raw:
                continue

            if raw.startswith("/"):
                await self._handle_command(raw)
            else:
                await self._handle_question(raw)

        print(f"\n{_DIM}Goodbye!{_RESET}")

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    async def _handle_command(self, raw: str) -> None:
        parts = raw.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("/quit", "/exit", "/q"):
            raise EOFError()

        elif cmd == "/help":
            print(HELP_TEXT)

        elif cmd == "/collection":
            if not arg:
                print(f"{_RED}Usage: /collection <name>{_RESET}")
                return
            self.collection = arg
            print(f"{_GREEN}Switched to collection '{arg}'.{_RESET}")

        elif cmd == "/collections":
            await self._list_collections()

        elif cmd == "/ingest":
            if not arg:
                print(f"{_RED}Usage: /ingest <text to ingest>{_RESET}")
                return
            await self._ingest_text(arg)

        elif cmd == "/ingest-file":
            if not arg:
                print(f"{_RED}Usage: /ingest-file <path>{_RESET}")
                return
            await self._ingest_file(arg)

        elif cmd == "/ingest-scraper":
            await self._ingest_scraper()

        elif cmd == "/delete":
            if not arg:
                print(f"{_RED}Usage: /delete <collection name>{_RESET}")
                return
            await self._delete_collection(arg)

        elif cmd == "/health":
            await self._show_health()

        else:
            print(f"{_RED}Unknown command: {cmd}. Type /help for commands.{_RESET}")

    async def _handle_question(self, question: str) -> None:
        print(f"{_DIM}Thinking...{_RESET}")
        try:
            result = await self.pipeline.ask(
                collection=self.collection,
                question=question,
            )
        except Exception as exc:
            print(f"{_RED}Error: {exc}{_RESET}")
            return

        print()
        print(_wrap(result["answer"]))
        print()

        sources = result.get("sources", [])
        if sources:
            print(f"{_DIM}Sources:{_RESET}")
            for s in sources:
                doc = s.get("doc_id", "?")[:20]
                score = s.get("score", 0)
                print(f"  {_DIM}• {doc} (score: {score:.3f}){_RESET}")
            print()

        elapsed = result.get("elapsed_ms", 0)
        print(f"{_DIM}[{elapsed:.0f}ms | {result.get('retrieved_count', 0)} chunks]{_RESET}")

    # ------------------------------------------------------------------
    # Sub-commands
    # ------------------------------------------------------------------

    async def _list_collections(self) -> None:
        names = await self.ingestor.store.list_collections()
        if not names:
            print(f"{_DIM}No collections yet. Use /ingest to add data.{_RESET}")
            return
        print(f"{_BOLD}Collections:{_RESET}")
        for name in names:
            count = await self.ingestor.store.collection_count(name)
            marker = f" {_GREEN}← current{_RESET}" if name == self.collection else ""
            print(f"  {_CYAN}{name}{_RESET} — {count} chunks{marker}")

    async def _ingest_text(self, text: str) -> None:
        print(f"{_DIM}Ingesting into '{self.collection}'...{_RESET}")
        try:
            result = await self.ingestor.ingest(
                collection=self.collection,
                text=text,
                doc_id=str(uuid.uuid4()),
            )
            print(
                f"{_GREEN}Done: {result['chunks_created']} chunks "
                f"({result['elapsed_ms']:.0f}ms){_RESET}"
            )
        except Exception as exc:
            print(f"{_RED}Ingest failed: {exc}{_RESET}")

    async def _ingest_file(self, path: str) -> None:
        from pathlib import Path

        p = Path(path)
        if not p.exists():
            print(f"{_RED}File not found: {path}{_RESET}")
            return
        if not p.is_file():
            print(f"{_RED}Not a file: {path}{_RESET}")
            return

        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"{_RED}Cannot read file as UTF-8: {path}{_RESET}")
            return

        print(
            f"{_DIM}Ingesting file '{p.name}' "
            f"({len(text)} chars) into '{self.collection}'...{_RESET}"
        )
        try:
            result = await self.ingestor.ingest(
                collection=self.collection,
                text=text,
                metadata={"source_file": str(p)},
                doc_id=p.stem,
            )
            print(
                f"{_GREEN}Done: {result['chunks_created']} chunks "
                f"({result['elapsed_ms']:.0f}ms){_RESET}"
            )
        except Exception as exc:
            print(f"{_RED}Ingest failed: {exc}{_RESET}")

    async def _ingest_scraper(self) -> None:
        print(f"{_DIM}Pulling data from scraper DB...{_RESET}")
        try:
            from chatbot.connectors.scraper_connector import run_scraper_ingest

            result = await run_scraper_ingest(collection=self.collection)
            print(
                f"{_GREEN}Done: {result['advertisers_processed']} advertisers → "
                f"{result['chunks_created']} chunks "
                f"({result['elapsed_ms']:.0f}ms){_RESET}"
            )
            if result.get("errors"):
                for err in result["errors"]:
                    print(f"  {_YELLOW}⚠ {err}{_RESET}")
        except ImportError:
            print(f"{_RED}Scraper connector not available (is the scraper DB present?).{_RESET}")
        except Exception as exc:
            print(f"{_RED}Scraper ingest failed: {exc}{_RESET}")

    async def _delete_collection(self, name: str) -> None:
        await self.ingestor.store.delete_collection(name)
        print(f"{_YELLOW}Deleted collection '{name}'.{_RESET}")
        if self.collection == name:
            self.collection = "default"
            print(f"{_YELLOW}Switched back to 'default'.{_RESET}")

    async def _show_health(self) -> None:
        print(f"{_DIM}Checking health...{_RESET}")
        try:
            health = await self.pipeline.health_check()
        except Exception as exc:
            print(f"{_RED}Health check failed: {exc}{_RESET}")
            return

        llm_status = f"{_GREEN}OK{_RESET}" if health["llm_ok"] else f"{_RED}FAIL{_RESET}"
        print(f"  LLM:         {llm_status} ({health.get('model', '?')})")
        print(f"  Collections: {len(health.get('collections', []))}")
        for name, count in health.get("collection_counts", {}).items():
            print(f"    {_CYAN}{name}{_RESET}: {count} chunks")


def _wrap(text: str, width: int = 80) -> str:
    """Wrap text for terminal display."""
    paragraphs = text.split("\n")
    wrapped = []
    for para in paragraphs:
        if para.strip():
            wrapped.append(textwrap.fill(para, width=width))
        else:
            wrapped.append("")
    return "\n".join(wrapped)


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Akirs RAG Chatbot — interactive CLI powered by Phi-4-mini via Ollama.",
    )
    parser.add_argument(
        "--collection",
        "-c",
        default="default",
        help="Initial collection to use (default: 'default').",
    )
    args = parser.parse_args()

    cli = ChatbotCLI(collection=args.collection)
    try:
        asyncio.run(cli.run())
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
