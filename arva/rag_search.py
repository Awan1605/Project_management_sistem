"""
RAG Semantic Search
====================
Service untuk melakukan semantic search menggunakan vector similarity.

Usage:
    from arva.rag_search import RAGSearch
    
    search = RAGSearch()
    results = search.search(query="progress project BAU", user=user, top_k=5)
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class RAGSearch:
    """
    Semantic Search Service untuk RAG system.
    
    Menggunakan vector similarity untuk menemukan 
    documents yang paling relevan dengan query.
    """
    
    def __init__(self, knowledge_base=None):
        """
        Initialize RAG Search.
        
        Args:
            knowledge_base: RAGKnowledgeBase instance (auto-init jika None)
        """
        if knowledge_base is None:
            from .rag_knowledge import get_rag_knowledge_base
            self.kb = get_rag_knowledge_base()
        else:
            self.kb = knowledge_base
    
    def search(
        self, 
        query: str, 
        user=None, 
        top_k: int = 5,
        filter_type: str = None
    ) -> List[Dict]:
        """
        Search untuk documents yang relevan dengan query.
        
        Args:
            query: Search query (natural language)
            user: User object (untuk filter by user)
            top_k: Jumlah results yang diinginkan
            filter_type: Filter by type ('project' atau 'task')
            
        Returns:
            List of dicts dengan format:
            [
                {
                    'document': 'text content',
                    'metadata': {...},
                    'distance': 0.123,
                    'relevance_score': 0.877
                }
            ]
        """
        try:
            # Generate embedding untuk query
            query_embedding = self.kb._generate_embedding(query)
            
            # Build where filter dengan OR logic untuk user access
            # User bisa akses: projects dimana mereka owner/member, tasks dimana mereka assignee/project owner
            where_filter = {}
            
            if filter_type:
                where_filter["type"] = filter_type
            
            # Perform search
            logger.info(f"[RAG Search] Query: '{query}' (top_k={top_k})")
            
            if user:
                # ChromaDB doesn't support complex OR filters in simple where clause
                # So we fetch more results and filter manually
                all_results = self.kb._collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k * 3  # Fetch more to have enough after filtering
                )
                
                # Manual filtering based on user access
                filtered_docs = []
                filtered_metadatas = []
                filtered_distances = []
                
                for doc, metadata, distance in zip(
                    all_results['documents'][0],
                    all_results['metadatas'][0],
                    all_results['distances'][0]
                ):
                    # Check if user has access
                    has_access = False
                    
                    if metadata.get('type') == 'project':
                        # User can access if they are owner or member
                        owner_id = metadata.get('owner_id')
                        member_ids_str = metadata.get('member_ids', '')
                        member_ids = [int(x) for x in member_ids_str.split(',') if x] if member_ids_str else []
                        
                        if owner_id == user.id or user.id in member_ids:
                            has_access = True
                    
                    elif metadata.get('type') == 'task':
                        # User can access if they are assignee or project owner
                        assignee_ids_str = metadata.get('assignee_ids', '')
                        assignee_ids = [int(x) for x in assignee_ids_str.split(',') if x] if assignee_ids_str else []
                        project_owner_id = metadata.get('project_owner_id')
                        
                        if user.id in assignee_ids or project_owner_id == user.id:
                            has_access = True
                    
                    if has_access:
                        filtered_docs.append(doc)
                        filtered_metadatas.append(metadata)
                        filtered_distances.append(distance)
                    
                    # Stop if we have enough results
                    if len(filtered_docs) >= top_k:
                        break
                
                # Prepare results in ChromaDB format
                results = {
                    'documents': [filtered_docs[:top_k]],
                    'metadatas': [filtered_metadatas[:top_k]],
                    'distances': [filtered_distances[:top_k]]
                }
            else:
                # No user filter - just use type filter if provided
                if where_filter:
                    results = self.kb._collection.query(
                        query_embeddings=[query_embedding],
                        n_results=top_k,
                        where=where_filter
                    )
                else:
                    results = self.kb._collection.query(
                        query_embeddings=[query_embedding],
                        n_results=top_k
                    )
            
            # Format results
            formatted_results = []
            
            for i, (doc, metadata, distance) in enumerate(
                zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )
            ):
                # Convert distance (lower is better) to relevance score (higher is better)
                # ChromaDB cosine distance: 0 = identical, 2 = opposite
                relevance_score = max(0, 1 - (distance / 2))
                
                formatted_results.append({
                    'rank': i + 1,
                    'document': doc,
                    'metadata': metadata,
                    'distance': distance,
                    'relevance_score': relevance_score,
                    'type': metadata.get('type', 'unknown')
                })
            
            logger.info(f"[RAG Search] Found {len(formatted_results)} results")
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"[RAG Search] Error during search: {e}")
            return []
    
    def search_projects(self, query: str, user=None, top_k: int = 3) -> List[Dict]:
        """
        Search khusus untuk projects.
        
        Args:
            query: Search query
            user: User object
            top_k: Number of results
            
        Returns:
            List of project documents
        """
        return self.search(query, user, top_k, filter_type='project')
    
    def search_tasks(self, query: str, user=None, top_k: int = 5) -> List[Dict]:
        """
        Search khusus untuk tasks.
        
        Args:
            query: Search query
            user: User object
            top_k: Number of results
            
        Returns:
            List of task documents
        """
        return self.search(query, user, top_k, filter_type='task')
    
    def build_context(
        self, 
        query: str, 
        user=None, 
        max_results: int = 5
    ) -> str:
        """
        Build context string dari search results.
        
        Ini yang akan diinjeksikan ke AI prompt.
        
        Args:
            query: User query
            user: User object
            max_results: Max number of results to include
            
        Returns:
            Formatted context string
        """
        results = self.search(query, user, top_k=max_results)
        
        if not results:
            return "Tidak ada data yang relevan ditemukan."
        
        # Build context
        context_parts = []
        
        for result in results:
            doc_type = result['type'].upper()
            relevance = result['relevance_score']
            
            context_parts.append(
                f"[{doc_type}] (Relevance: {relevance:.1%})\n{result['document']}"
            )
        
        context = "\n\n---\n\n".join(context_parts)
        
        logger.info(f"[RAG Search] Built context: {len(results)} documents, {len(context)} chars")
        
        return context
    
    def get_stats(self) -> Dict:
        """
        Get knowledge base statistics.
        
        Returns:
            Dict dengan statistik
        """
        try:
            total_docs = self.kb.get_document_count()
            
            # Count by type
            all_data = self.kb._collection.get()
            type_counts = {'project': 0, 'task': 0}
            
            for metadata in all_data['metadatas']:
                doc_type = metadata.get('type', 'unknown')
                if doc_type in type_counts:
                    type_counts[doc_type] += 1
            
            return {
                'total_documents': total_docs,
                'projects': type_counts['project'],
                'tasks': type_counts['task']
            }
            
        except Exception as e:
            logger.error(f"[RAG Search] Error getting stats: {e}")
            return {
                'total_documents': 0,
                'projects': 0,
                'tasks': 0
            }


# Singleton instance
_rag_search_instance = None

def get_rag_search() -> RAGSearch:
    """
    Factory function untuk mendapatkan RAG Search instance.
    """
    global _rag_search_instance
    
    if _rag_search_instance is None:
        _rag_search_instance = RAGSearch()
    
    return _rag_search_instance
