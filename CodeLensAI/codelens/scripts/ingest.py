import os
import sys
import argparse

# Add workspace root to sys.path to allow absolute imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from codelens.src.config.settings import get_settings
from codelens.src.memory.vector_store import VectorStore, OllamaEmbeddingFunction
from codelens.src.llm.ollama_client import OllamaClient
from codelens.src.models import DocChunk, SourceType

def chunk_text(text: str) -> list[str]:
    raw_chunks = [c.strip() for c in text.split("\n\n") if c.strip()]
    chunks = []
    current_chunk = ""
    for rc in raw_chunks:
        if not current_chunk:
            current_chunk = rc
        else:
            if len(current_chunk) < 200:
                current_chunk = f"{current_chunk}\n\n{rc}"
            else:
                chunks.append(current_chunk)
                current_chunk = rc
        
        while len(current_chunk) > 800:
            chunks.append(current_chunk[:800])
            current_chunk = current_chunk[800:]
            
    if current_chunk:
        chunks.append(current_chunk)
    return chunks

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest architectural docs, standards, or PR examples into vector store.")
    parser.add_argument("--source", type=str, required=True, help="Directory path to ingest documents from.")
    parser.add_argument("--type", type=str, required=True, choices=["arch_doc", "standard", "pr_example"], help="Source type of the documents.")
    parser.add_argument("--collection", type=str, default=None, help="ChromaDB collection override.")
    
    args = parser.parse_args()
    
    # Resolve collection name
    type_to_collection = {
        "arch_doc": "arch_docs",
        "standard": "standards",
        "pr_example": "pr_examples"
    }
    collection_name = args.collection or type_to_collection[args.type]
    source_type_enum = SourceType(args.type.upper())
    
    if not os.path.exists(args.source):
        print(f"Error: Source directory '{args.source}' does not exist.")
        sys.exit(1)
        
    settings = get_settings()

    # Initialize Ollama client and unified embedding function
    ollama_client = OllamaClient(
        base_url=settings.OLLAMA_BASE_URL,
        model_code=settings.OLLAMA_MODEL_CODE,
        model_reason=settings.OLLAMA_MODEL_REASON,
        embed_model=settings.OLLAMA_EMBED_MODEL
    )
    embedding_fn = OllamaEmbeddingFunction(ollama_client=ollama_client)
    vector_store = VectorStore(path=settings.CHROMA_PATH, embedding_function=embedding_fn)

    chunks_to_ingest = []
    file_count = 0
    
    # Recursively find md and txt files
    for root, _, files in os.walk(args.source):
        for file in files:
            if file.endswith((".md", ".txt")):
                file_path = os.path.join(root, file)
                file_count += 1
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    file_chunks = chunk_text(content)
                    
                    for idx, chunk_content in enumerate(file_chunks):
                        chunk_id = f"{os.path.basename(file_path)}_{idx}"
                        doc_chunk = DocChunk(
                            chunk_id=chunk_id,
                            content=chunk_content,
                            source_type=source_type_enum,
                            metadata={"file_path": file_path}
                        )
                        chunks_to_ingest.append(doc_chunk)
                except Exception as e:
                    print(f"Warning: Failed to process file '{file_path}': {e}")
                    
    if not chunks_to_ingest:
        print("No documents found or chunked for ingestion.")
        return
        
    # Embeddings are now generated automatically by ChromaDB via the
    # OllamaEmbeddingFunction, ensuring the same model is used for both
    # ingestion and retrieval. No need to pre-compute embeddings here.
    print(f"Ingesting {len(chunks_to_ingest)} chunks from {file_count} files into collection '{collection_name}'...")
    print(f"Using Ollama embed model: {settings.OLLAMA_EMBED_MODEL}")
    vector_store.add_documents(collection_name, chunks_to_ingest)
    
    print(f"Successfully ingested {len(chunks_to_ingest)} chunks from {file_count} files into collection '{collection_name}'")

if __name__ == "__main__":
    main()
