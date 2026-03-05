import json
import os
from typing import Dict, List, Optional
from django.utils import timezone
from datetime import timedelta
from google import genai
from django.conf import settings
from django.db import models


class GeminiService:
    """Service for AI-powered task priority analysis using Google Gemini."""
    
    def __init__(self):
        api_key = getattr(settings, 'GEMINI_API_KEY', os.environ.get('GEMINI_API_KEY'))
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured")
        # Initialize client with v1 API
        self.client = genai.Client(api_key=api_key, http_options={'api_version': 'v1'})
        # Use gemini-2.5-flash (latest available model with quota)
        self.model_name = 'gemini-2.5-flash'
    
    def _build_task_context(self, task) -> Dict:
        """Build comprehensive context for a task."""
        from .models import Task
        
        checklist_items = list(task.checklist_items.all())
        checklist_progress = {
            'total': len(checklist_items),
            'done': sum(1 for item in checklist_items if item.is_done),
            'items': [item.content for item in checklist_items]
        }
        
        # Calculate days until due
        days_until_due = None
        urgency_indicator = ""
        if task.due_date:
            days_until_due = (task.due_date - timezone.localdate()).days
            if days_until_due < 0:
                urgency_indicator = "OVERDUE"
            elif days_until_due == 0:
                urgency_indicator = "DUE TODAY"
            elif days_until_due <= 2:
                urgency_indicator = "URGENT"
        
        # Get dependencies (tasks that depend on this one)
        # For now, we'll use a simple heuristic based on description mentions
        dependencies = []
        
        return {
            'id': task.id,
            'title': task.title,
            'description': task.description or "",
            'due_date': str(task.due_date) if task.due_date else None,
            'days_until_due': days_until_due,
            'urgency_indicator': urgency_indicator,
            'current_priority': task.priority,
            'project_name': task.project.name,
            'assignees': [u.username for u in task.assignees.all()],
            'checklist_progress': checklist_progress,
            'labels': [label.name for label in task.labels.all()],
            'is_archived': task.is_archived,
            'created_at': str(task.created_at),
            'task_list': task.task_list.name if task.task_list else None,
        }
    
    def _build_analysis_prompt(self, task_context: Dict) -> str:
        """Build the AI prompt for task priority analysis."""
        prompt = f"""Analisis task berikut dan berikan prioritas komprehensif.

TASK INFORMATION:
Title: {task_context['title']}
Description: {task_context['description']}
Project: {task_context['project_name']}
Current Status: {task_context['task_list']}

DEADLINE ANALYSIS:
Due Date: {task_context['due_date'] or 'No deadline set'}
Days Until Due: {task_context['days_until_due'] if task_context['days_until_due'] is not None else 'N/A'}
Urgency: {task_context['urgency_indicator'] or 'Normal'}

WORK BREAKDOWN:
Checklist Progress: {task_context['checklist_progress']['done']}/{task_context['checklist_progress']['total']} completed
Checklist Items: {', '.join(task_context['checklist_progress']['items'][:5]) if task_context['checklist_progress']['items'] else 'None'}

ASSIGNMENT:
Assignees: {', '.join(task_context['assignees']) if task_context['assignees'] else 'Unassigned'}
Labels: {', '.join(task_context['labels']) if task_context['labels'] else 'None'}

ANALYSIS CRITERIA:
1. Deadline Urgency (40%): Tasks nearing deadline get higher priority
2. Complexity/Scope (25%): More complex tasks may need earlier start
3. Dependencies Impact (20%): Tasks blocking others are critical
4. Current Progress (15%): Nearly complete tasks might be prioritized to finish

Provide analysis in this exact JSON format:
{{
  "priority_score": <number 1-100>,
  "priority_level": "Critical|High|Medium|Low",
  "complexity": "High|Medium|Low",
  "estimated_hours": <number or null>,
  "reasoning": "<detailed explanation in Indonesian>",
  "recommended_action": "<specific advice in Indonesian>",
  "factors": {{
    "deadline_urgency": <score 1-100>,
    "complexity_score": <score 1-100>,
    "dependency_impact": <score 1-100>,
    "progress_factor": <score 1-100>
  }}
}}

Respond ONLY with the JSON, no other text."""
        return prompt
    
    def analyze_task(self, task) -> Dict:
        """Analyze a single task and return priority recommendations."""
        try:
            context = self._build_task_context(task)
            prompt = self._build_analysis_prompt(context)
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            response_text = response.text.strip()
            
            # Extract JSON from response (handle markdown code blocks)
            if '```json' in response_text:
                json_str = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                json_str = response_text.split('```')[1].split('```')[0].strip()
            else:
                json_str = response_text
            
            result = json.loads(json_str)
            
            # Add metadata
            result['task_id'] = task.id
            result['analyzed_at'] = str(timezone.now())
            
            return result
            
        except json.JSONDecodeError as e:
            return {
                'error': 'Failed to parse AI response',
                'raw_response': response_text if 'response_text' in locals() else str(e),
                'task_id': task.id
            }
        except Exception as e:
            return {
                'error': str(e),
                'task_id': task.id
            }
    
    def analyze_multiple_tasks(self, tasks: List) -> List[Dict]:
        """Analyze multiple tasks and return sorted priority list."""
        results = []
        for task in tasks:
            analysis = self.analyze_task(task)
            if 'error' not in analysis:
                results.append(analysis)
        
        # Sort by priority score (descending)
        results.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
        return results
    
    def get_priority_queue(self, user, project=None, limit=20) -> List[Dict]:
        """Get prioritized queue of tasks for a user."""
        from .models import Task
        
        # Get tasks assigned to user or in user's projects
        tasks = Task.objects.filter(
            is_archived=False
        ).filter(
            models.Q(assignees=user) | models.Q(project__owner=user)
        ).exclude(
            task_list__name__iexact='Done'
        ).select_related(
            'project', 'task_list'
        ).prefetch_related(
            'assignees', 'labels', 'checklist_items'
        )
        
        if project:
            tasks = tasks.filter(project=project)
        
        tasks = tasks[:limit]
        return self.analyze_multiple_tasks(tasks)


def get_ai_service() -> GeminiService:
    """Factory function to get AI service instance."""
    return GeminiService()


class AIChatService:
    """Service for AI Chat Assistant with context awareness."""
    
    def __init__(self):
        api_key = getattr(settings, 'GEMINI_API_KEY', os.environ.get('GEMINI_API_KEY'))
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured")
        # Initialize client with v1 API
        self.client = genai.Client(api_key=api_key, http_options={'api_version': 'v1'})
        # Use gemini-2.5-flash (latest available model with quota)
        self.model_name = 'gemini-2.5-flash'
    
    def _get_user_tasks_context(self, user) -> str:
        """Get formatted context of user's tasks."""
        from .models import Task
        
        tasks = Task.objects.filter(
            is_archived=False
        ).filter(
            models.Q(assignees=user) | models.Q(project__owner=user)
        ).exclude(
            task_list__name__iexact='Done'
        ).select_related(
            'project', 'task_list'
        ).prefetch_related(
            'assignees', 'labels', 'checklist_items'
        ).order_by('due_date')[:20]
        
        if not tasks:
            return "Tidak ada tugas yang sedang aktif untuk user ini."
        
        context_parts = []
        for i, task in enumerate(tasks, 1):
            checklist_items = list(task.checklist_items.all())
            checklist_done = sum(1 for item in checklist_items if item.is_done)
            checklist_total = len(checklist_items)
            
            due_info = ""
            if task.due_date:
                days_until = (task.due_date - timezone.localdate()).days
                if days_until < 0:
                    due_info = f" (OVERDUE {abs(days_until)} hari)"
                elif days_until == 0:
                    due_info = " (DUE TODAY)"
                else:
                    due_info = f" ({days_until} hari lagi)"
            
            task_info = f"""
{i}. {task.title}
   Project: {task.project.name}
   Status: {task.task_list.name}
   Priority: {task.get_priority_display()}
   Due: {task.due_date.strftime('%d %b %Y') if task.due_date else 'Tidak ada deadline'}{due_info}
   Progress: {checklist_done}/{checklist_total} checklist completed
   Description: {task.description[:100] if task.description else 'Tidak ada deskripsi'}..."""
            context_parts.append(task_info)
        
        return "\n".join(context_parts)
    
    def _build_system_prompt(self, user) -> str:
        """Build system prompt with user context."""
        tasks_context = self._get_user_tasks_context(user)
        
        return f"""Kamu adalah AI Task Assistant yang membantu user mengelola prioritas pekerjaan mereka. 

INFORMASI USER:
Username: {user.username}
Nama: {user.get_full_name() or user.username}

DAFTAR TUGAS USER SAAT INI:
{tasks_context}

PERAN KAMU:
1. Berikan rekomendasi prioritas tugas berdasarkan deadline, kompleksitas, dan urgensi
2. Jawab pertanyaan user tentang tugas mereka
3. Berikan saran produktivitas dan time management
4. Bantu analisis jika user bingung mau mengerjakan apa dulu

ATURAN:
- Selalu jawab dalam Bahasa Indonesia yang ramah dan profesional
- Berikan respons yang konkret dan actionable
- Jika user tanya "apa yang harus saya kerjakan hari ini", analisis tugas dengan deadline terdekat
- Jika ada tugas overdue, segera ingatkan user
- Bantu breakdown tugas kompleks menjadi langkah-langkah kecil
- Jangan membuat informasi tugas palsu - hanya gunakan data yang diberikan di atas

Selalu ingat: Kamu hanya bisa melihat tugas user di atas. Jangan berikan informasi tentang tugas lain yang tidak ada di daftar."""
    
    def chat(self, user, message: str, chat_history: List[Dict] = None) -> str:
        """Process chat message and return AI response."""
        try:
            # Build system prompt
            system_prompt = self._build_system_prompt(user)
            
            # Build conversation content for new API
            # New API expects either a simple string or properly structured content
            full_prompt = f"""{system_prompt}

User: {message}

Assistant:"""
            
            # Add chat history if exists
            if chat_history:
                for msg in chat_history[-10:]:  # Keep last 10 messages for context
                    if msg['role'] == 'user':
                        full_prompt += f"\nUser: {msg['content']}"
                    else:
                        full_prompt += f"\nAssistant: {msg['content']}"
                
                full_prompt += f"\nAssistant:"
            
            # Generate response using new API - pass as simple string
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt
            )
            return response.text.strip()
            
        except Exception as e:
            return f"Maaf, terjadi kesalahan: {str(e)}. Silakan coba lagi."
    
    def get_work_recommendation(self, user) -> str:
        """Get AI recommendation for today's work."""
        prompt = "Berdasarkan daftar tugas saya, apa yang harus saya kerjakan hari ini? Berikan prioritas dan alasannya."
        return self.chat(user, prompt)


def get_ai_chat_service() -> AIChatService:
    """Factory function to get AI chat service instance."""
    return AIChatService()