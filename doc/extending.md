# Extending ChatPDF

## Adding a new LLM provider

1. Add the LangChain package: `uv add langchain-<provider>`
2. Add a branch in `services/llm_gateway.py → LLMGateway.get_llm`
3. Add the API key to `config.py` + `.env.example`
4. Write a unit test in `tests/unit/` mocking the new provider

## Adding a new RAG plugin (chunker / retriever / reranker)

1. Create a subclass of `BaseChunker` / `BaseRetriever` / `BaseReranker` in `services/plugins/`
2. Register it in `services/rag_config.py` in the appropriate `_*_registry()` function
3. Write a unit test in `tests/unit/test_rag_config.py`

No changes to LangGraph or router code needed.
