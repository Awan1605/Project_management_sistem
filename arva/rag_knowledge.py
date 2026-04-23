"""
RAG Knowledge Base
===================
Module untuk mengelola vector database dan embedding untuk sistem RAG.

Komponen:
1. Embedding Model: Mengubah teks menjadi vector
2. Vector Database (ChromaDB): Menyimpan dan mencari vectors
3. Document Management: CRUD operations untuk documents

Usage:
    from arva.rag_knowledge import RAGKnowledgeBase
    
    kb = RAGKnowledgeBase()
    kb.add_project(project_instance)
    kb.add_task(task_instance)
"""

import os
import logging
from typing import List, Dict, Optional
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


class RAGKnowledgeBase:
    """
    Knowledge Base untuk RAG system.
    
    Menggunakan ChromaDB sebagai vector database dan 
    fastembed untuk embedding model (lebih ringan dari sentence-transformers).
    """
    
    def __init__(self):
        """Initialize RAG Knowledge Base"""
        self._client = None
        self._collection = None
        self._embedding_model = None
        
        # Path untuk persist ChromaDB
        self.persist_directory = Path(settings.BASE_DIR) / '.rag_chromadb'
        self.persist_directory.mkdir(exist_ok=True)
        
        # Initialize components
        self._initialize_embedding_model()
        self._initialize_vector_db()
    
    def _initialize_embedding_model(self):
        """Initialize embedding model (fastembed - lebih ringan dari sentence-transformers)"""
        try:
            from fastembed import TextEmbedding
            
            # Model kecil dan cepat untuk production
            model_name = 'BAAI/bge-small-en-v1.5'
            logger.info(f"[RAG] Loading embedding model: {model_name}")
            
            self._embedding_model = TextEmbedding(model_name=model_name)
            logger.info("[RAG] Embedding model loaded successfully")
            
        except ImportError:
            logger.error("[RAG] fastembed not installed. Run: pip install fastembed")
            raise
        except Exception as e:
            logger.error(f"[RAG] Error loading embedding model: {e}")
            raise
    
    def _initialize_vector_db(self):
        """Initialize ChromaDB vector database dengan custom embedding (fastembed)"""
        try:
            import chromadb
            
            logger.info(f"[RAG] Initializing ChromaDB at: {self.persist_directory}")
            
            # Configure ChromaDB settings to avoid downloading default models
            chroma_settings = chromadb.config.Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
            
            # Persistent client (data tersimpan di disk)
            self._client = chromadb.PersistentClient(
                path=str(self.persist_directory),
                settings=chroma_settings
            )
            
            # Get or create collection - TANPA embedding function (kita pakai custom)
            collection_name = "kanban_knowledge"
            
            # Cek apakah collection sudah ada
            existing_collections = [c.name for c in self._client.list_collections()]
            
            if collection_name in existing_collections:
                logger.info(f"[RAG] Using existing collection: {collection_name}")
                self._collection = self._client.get_collection(collection_name)
            else:
                logger.info(f"[RAG] Creating new collection: {collection_name}")
                # Create collection WITHOUT embedding function
                # We use our own embeddings from fastembed
                self._collection = self._client.create_collection(
                    name=collection_name,
                    metadata={
                        "hnsw:space": "cosine",  # Cosine similarity
                        "embedding:dimension": 384  # BAAI/bge-small-en-v1.5 dimension
                    }
                )
            
            logger.info(f"[RAG] ChromaDB initialized. Documents: {self._collection.count()}")

        except ImportError:
            logger.error("[RAG] chromadb not installed. Run: pip install chromadb")
            raise
        except Exception as e:
            logger.error(f"[RAG] Error initializing ChromaDB: {e}")
            raise
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding untuk text menggunakan fastembed.
        
        Args:
            text: Text yang akan di-embed
            
        Returns:
            List of floats (vector embedding)
        """
        # fastembed returns an iterator of numpy arrays
        embeddings = list(self._embedding_model.embed([text]))
        return embeddings[0].tolist()
    
    def add_project(self, project) -> str:
        """
        Add project ke knowledge base.
        
        Args:
            project: Django Project instance
            
        Returns:
            Document ID
        """
        try:
            # Build document
            total_tasks = project.tasks.count()
            completed_tasks = project.tasks.filter(task_list__name__iexact='Done').count()
            progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            # Get all member IDs
            member_ids = list(project.memberships.values_list('user_id', flat=True))
            all_user_ids = [project.owner.id] + member_ids
            
            doc = f"""Project: {project.name}
Description: {project.description or 'No description'}
Status: {'Closed' if getattr(project, 'is_closed', False) else 'Active'}
Progress: {progress:.1f}% ({completed_tasks}/{total_tasks} tasks completed)
Owner: {project.owner.username}
ETD: {getattr(project, 'etd', 'Not set')}
Members: {', '.join([m.user.username for m in project.memberships.all()])}
"""
            
            # Generate embedding
            embedding = self._generate_embedding(doc)
            
            # Add to ChromaDB
            doc_id = f"project_{project.id}"
            self._collection.upsert(
                embeddings=[embedding],
                documents=[doc],
                metadatas=[{
                    "type": "project",
                    "id": project.id,
                    "owner_id": project.owner.id,
                    "member_ids": ",".join(map(str, all_user_ids)),  # Store as comma-separated for filtering
                    "name": project.name,
                    "progress": progress
                }],
                ids=[doc_id]
            )
            
            logger.info(f"[RAG] Added project to KB: {project.name} (ID: {doc_id})")
            return doc_id
            
        except Exception as e:
            logger.error(f"[RAG] Error adding project to KB: {e}")
            raise
    
    def add_task(self, task) -> str:
        """
        Add task ke knowledge base.
        
        Args:
            task: Django Task instance
            
        Returns:
            Document ID
        """
        try:
            # Build checklist text
            checklist_items = list(task.checklist_items.all())
            checklist_text = "\n".join([
                f"  - {item.content}: {'Done' if item.is_done else 'Pending'}"
                for item in checklist_items
            ])
            
            # Build attachments text
            attachments = list(task.attachments.all())
            attachments_text = "\n".join([
                f"  - {att.file.name} (uploaded by {att.uploaded_by.username if att.uploaded_by else 'unknown'} on {att.uploaded_at.date()})"
                for att in attachments
            ]) if attachments else "  No attachments"
            
            # Extract attachment content for RAG
            attachments_content = []
            for att in attachments:
                try:
                    from .document_extractor import get_file_summary
                    file_path = att.file.path
                    content = get_file_summary(file_path, max_length=1500)
                    if content and content != "[No text content could be extracted]":
                        attachments_content.append(f"\n--- Content from {att.file.name} ---\n{content}")
                except Exception as e:
                    logger.error(f"[RAG] Error extracting attachment {att.file.name}: {e}")

            attachments_content_text = "\n".join(attachments_content) if attachments_content else ""

            # Get all relevant user IDs
            assignee_ids = list(task.assignees.values_list('id', flat=True))
            all_user_ids = list(set([task.project.owner.id, task.project.id] + assignee_ids))
            
            # Build document
            doc = f"""Task: {task.title}
Description: {task.description or 'No description'}
Project: {task.project.name}
Status: {task.task_list.name if task.task_list else 'No status'}
Priority: {getattr(task, 'priority', 'Not set')}
Deadline: {task.due_date or 'No deadline'}
Assignees: {', '.join([u.username for u in task.assignees.all()])}
Checklist:
{checklist_text if checklist_items else '  No checklist items'}
Attachments:
{attachments_text}
{attachments_content_text}
Created: {task.created_at}
"""
            
            # Generate embedding
            embedding = self._generate_embedding(doc)
            
            # Add to ChromaDB
            doc_id = f"task_{task.id}"
            self._collection.upsert(
                embeddings=[embedding],
                documents=[doc],
                metadatas=[{
                    "type": "task",
                    "id": task.id,
                    "project_id": task.project.id,
                    "project_owner_id": task.project.owner.id,
                    "assignee_ids": ",".join(map(str, assignee_ids)) if assignee_ids else "",
                    "title": task.title,
                    "status": task.task_list.name if task.task_list else 'Unknown'
                }],
                ids=[doc_id]
            )
            
            logger.info(f"[RAG] Added task to KB: {task.title} (ID: {doc_id})")
            return doc_id
            
        except Exception as e:
            logger.error(f"[RAG] Error adding task to KB: {e}")
            raise
    
    def remove_document(self, doc_id: str):
        """
        Remove document dari knowledge base.
        
        Args:
            doc_id: Document ID (e.g., 'project_123', 'task_456')
        """
        try:
            self._collection.delete(ids=[doc_id])
            logger.info(f"[RAG] Removed document: {doc_id}")
        except Exception as e:
            logger.error(f"[RAG] Error removing document {doc_id}: {e}")
            raise
    
    def get_document_count(self) -> int:
        """Get total documents in knowledge base"""
        return self._collection.count()
    
    def clear_all(self):
        """Clear all documents (untuk reset/testing)"""
        try:
            all_ids = self._collection.get()['ids']
            if all_ids:
                self._collection.delete(ids=all_ids)
                logger.info("[RAG] Cleared all documents from KB")
        except Exception as e:
            logger.error(f"[RAG] Error clearing KB: {e}")
            raise


# Singleton instance
_rag_kb_instance = None

def get_rag_knowledge_base() -> RAGKnowledgeBase:
    """
    Factory function untuk mendapatkan RAG Knowledge Base instance.
    Menggunakan singleton pattern agar tidak re-init berkali-kali.
    """
    global _rag_kb_instance
    
    if _rag_kb_instance is None:
        _rag_kb_instance = RAGKnowledgeBase()
    
    return _rag_kb_instance
