import chromadb
import logging
from typing import List, Dict, Optional, Any
from ..models import DocChunk

logger = logging.getLogger(__name__)


class OllamaEmbeddingFunction(chromadb.EmbeddingFunction):
    """Custom ChromaDB embedding function that delegates to the local Ollama service.

    This ensures the same embedding model (e.g. nomic-embed-text) is used for both
    ingestion and retrieval, preventing dimension-mismatch errors that occur when
    ChromaDB's default embedding model differs from the one used during ingestion.
    """

    def __init__(self, ollama_client: Any) -> None:
        """
        Initialize with an OllamaClient instance.

        Args:
            ollama_client: An instance of OllamaClient with an embed() method.
        """
        self.ollama_client = ollama_client

    def __call__(self, input: chromadb.Documents) -> chromadb.Embeddings:
        """
        Generate embeddings for the given documents using the Ollama embed model.

        Args:
            input: List of text strings to embed.

        Returns:
            A list of float-list embeddings.
        """
        return self.ollama_client.embed(list(input))


class VectorStore:
    """ChromaDB wrapper for storing and querying documentation and code chunk embeddings."""

    def __init__(self, path: str, embedding_function: Optional[chromadb.EmbeddingFunction] = None) -> None:
        """
        Initialize the VectorStore with a persistence path and optional embedding function.

        Args:
            path: Local path where ChromaDB databases are stored.
            embedding_function: Optional custom embedding function for collections.
                                When provided, all collections will use this function
                                for both ingestion and retrieval, ensuring a unified
                                embedding space.
        """
        self.client = chromadb.PersistentClient(path=path)
        self.embedding_function = embedding_function

    def get_or_create_collection(self, name: str) -> Any:
        """
        Retrieve or create a Chroma collection by name.

        Args:
            name: The name of the collection (e.g. 'arch_docs').

        Returns:
            The Chroma collection object.
        """
        kwargs = {"name": name}
        if self.embedding_function is not None:
            kwargs["embedding_function"] = self.embedding_function
        return self.client.get_or_create_collection(**kwargs)

    def add_documents(self, collection_name: str, chunks: List[DocChunk], embeddings: Optional[List[List[float]]] = None) -> None:
        """
        Add documentation chunks to a collection.

        Args:
            collection_name: Target collection name.
            chunks: A list of DocChunk instances to add.
            embeddings: Optional pre-computed embeddings for the chunks.
                        When None and an embedding_function is set, ChromaDB will
                        use the embedding_function to generate embeddings automatically.
        """
        collection = self.get_or_create_collection(collection_name)
        
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_embeddings = embeddings[i:i + batch_size] if embeddings is not None else None
            
            ids = [c.chunk_id for c in batch]
            documents = [c.content for c in batch]
            metadatas = []
            for c in batch:
                meta = {
                    "source_type": str(c.source_type),
                    "chunk_id": c.chunk_id,
                }
                if c.metadata:
                    for k, v in c.metadata.items():
                        meta[k] = str(v)
                metadatas.append(meta)
                
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=batch_embeddings
            )
        logger.info(f"Added {len(chunks)} documents to collection: {collection_name}")


    def query(self, collection_name: str, query_text: str, n_results: int = 5) -> List[DocChunk]:
        """
        Query a collection using a search string.

        Args:
            collection_name: Target collection name.
            query_text: Natural language query string.
            n_results: Number of results to return.

        Returns:
            A list of matching DocChunk instances.
        """
        collection = self.get_or_create_collection(collection_name)
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        
        if not results or not results.get("documents") or not results["documents"][0]:
            return []
            
        doc_chunks = []
        documents = results["documents"][0]
        metadatas = results["metadatas"][0] if results.get("metadatas") else [None] * len(documents)
        ids = results["ids"][0] if results.get("ids") else [f"doc_{idx}" for idx in range(len(documents))]
        
        for idx in range(len(documents)):
            meta = metadatas[idx] or {}
            chunk_id = meta.get("chunk_id", ids[idx])
            source_type = meta.get("source_type", "ARCH_DOC")
            
            extra_meta = {k: v for k, v in meta.items() if k not in ["source_type", "chunk_id"]}
            
            doc_chunks.append(DocChunk(
                chunk_id=chunk_id,
                content=documents[idx],
                source_type=source_type,
                metadata=extra_meta
            ))
            
        return doc_chunks

    def query_by_embedding(self, collection_name: str, embedding: List[float], n_results: int = 5) -> List[DocChunk]:
        """
        Query a collection using a pre-computed vector embedding.

        Args:
            collection_name: Target collection name.
            embedding: The raw vector embedding float list.
            n_results: Number of results to return.

        Returns:
            A list of matching DocChunk instances.
        """
        collection = self.get_or_create_collection(collection_name)
        results = collection.query(
            query_embeddings=[embedding],
            n_results=n_results
        )
        
        if not results or not results.get("documents") or not results["documents"][0]:
            return []
            
        doc_chunks = []
        documents = results["documents"][0]
        metadatas = results["metadatas"][0] if results.get("metadatas") else [None] * len(documents)
        ids = results["ids"][0] if results.get("ids") else [f"doc_{idx}" for idx in range(len(documents))]
        
        for idx in range(len(documents)):
            meta = metadatas[idx] or {}
            chunk_id = meta.get("chunk_id", ids[idx])
            source_type = meta.get("source_type", "ARCH_DOC")
            
            extra_meta = {k: v for k, v in meta.items() if k not in ["source_type", "chunk_id"]}
            
            doc_chunks.append(DocChunk(
                chunk_id=chunk_id,
                content=documents[idx],
                source_type=source_type,
                metadata=extra_meta
            ))
            
        return doc_chunks

    def count(self, collection_name: str) -> int:
        """
        Get the total document count in a collection.

        Args:
            collection_name: Target collection name.

        Returns:
            The count of documents.
        """
        collection = self.get_or_create_collection(collection_name)
        return collection.count()

    def delete_collection(self, collection_name: str) -> None:
        """
        Delete a collection by name.

        Args:
            collection_name: The name of the collection to delete.
        """
        self.client.delete_collection(name=collection_name)
        logger.info(f"Deleted collection: {collection_name}")
