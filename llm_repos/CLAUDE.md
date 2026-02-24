# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This directory contains a collection of cloned LLM-related repositories for reference and study. Each subdirectory is an independent project with its own build system, tests, and documentation.

## Repository Overview

| Directory | Description |
|-----------|-------------|
| `langchain-master` | LangChain framework for LLM applications (Python monorepo) |
| `llama_index-main` | LlamaIndex data framework for LLM apps (Python) |
| `ollama-main` | Local LLM inference server (Go + TypeScript UI) |
| `vllm-main` | High-performance LLM inference engine (Python/C++) |
| `open-webui-main` | Web UI for LLM interaction (Python/TypeScript) |
| `anything-llm-master` | All-in-one document chat app (Node.js) |
| `ragflow-main` | RAG engine with document understanding (Python) |
| `mem0-main` | Memory layer for AI applications (Python) |
| `khoj-master` | AI personal assistant (Python) |
| `LlamaFactory-main` | LLM fine-tuning framework (Python) |
| `milvus-master` | Vector database (Go) |
| `graphrag-main` | Microsoft's GraphRAG (Python) |
| `inference-main` | Xinference model serving (Python) |
| `lmdeploy-main` | LMDeploy inference deployment (Python/C++) |
| `pathway-main` | Real-time data pipelines (Rust/Python) |
| `mindsdb-main` | AI tables/database integration (Python) |
| `opencompass-main` | Model evaluation toolkit (Python) |
| `self-llm_HOW-TO` | Chinese LLM tutorials and guides |

## Working Within Subdirectories

Each repository is independent. When working within one:

1. Check for its own `README.md`, `CLAUDE.md`, or `.cursorrules`
2. Look for build/test commands in:
   - Python: `pyproject.toml`, `setup.py`, `Makefile`
   - Node.js: `package.json`
   - Go: `Makefile`, `go.mod`
   - Rust: `Cargo.toml`

3. Common patterns:
   - **LangChain/LlamaIndex**: `make lint`, `make test`, `pytest`
   - **Go projects**: `make build`, `make test`
   - **Node.js projects**: `npm run build`, `npm test`
   - **Python projects**: `pip install -e .`, `pytest`

## Notes

- No unified build system exists at this level
- Each subdirectory should be treated as a separate repository
- Some repos have monorepo structures with multiple packages/libs
