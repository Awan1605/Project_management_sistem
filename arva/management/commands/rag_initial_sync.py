"""
Django Management Command: rag_initial_sync
=============================================
Sync semua project dan task existing ke RAG Knowledge Base.

Usage:
    python manage.py rag_initial_sync
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from arva.models import Project, Task
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync all existing projects and tasks to RAG Knowledge Base'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing RAG data before sync',
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='Show RAG statistics after sync',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting RAG Initial Sync...'))
        
        # Check if RAG is enabled
        if not getattr(settings, 'USE_RAG', False):
            self.stdout.write(self.style.WARNING('⚠️  RAG is not enabled (USE_RAG=False)'))
            self.stdout.write(self.style.WARNING('   Set USE_RAG=True in settings.py or .env file'))
            return
        
        try:
            from arva.rag_knowledge import get_rag_knowledge_base
            rag_kb = get_rag_knowledge_base()
        except Exception as e:
            raise CommandError(f'Failed to initialize RAG: {e}')
        
        # Clear existing data if requested
        if options['clear']:
            self.stdout.write(self.style.WARNING('🗑️  Clearing existing RAG data...'))
            rag_kb.clear_all()
            self.stdout.write(self.style.SUCCESS('✓ Cleared'))
        
        # Sync Projects
        self.stdout.write('\n📁 Syncing Projects...')
        projects = Project.objects.all()
        project_count = 0
        
        for project in projects:
            try:
                rag_kb.add_project(project)
                project_count += 1
                self.stdout.write(f'  ✓ {project.name}')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ {project.name}: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'✓ Synced {project_count} projects'))
        
        # Sync Tasks
        self.stdout.write('\n📋 Syncing Tasks...')
        tasks = Task.objects.select_related('project', 'task_list').prefetch_related(
            'assignees', 'checklist_items'
        )
        task_count = 0
        
        for task in tasks:
            try:
                rag_kb.add_task(task)
                task_count += 1
                if task_count % 10 == 0:
                    self.stdout.write(f'  ... {task_count} tasks synced')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Task {task.id}: {e}'))
        
        self.stdout.write(self.style.SUCCESS(f'✓ Synced {task_count} tasks'))
        
        # Show stats
        if options['stats'] or True:  # Always show stats
            from arva.rag_search import get_rag_search
            rag_search = get_rag_search()
            stats = rag_search.get_stats()
            
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('📊 RAG Knowledge Base Statistics'))
            self.stdout.write('='*60)
            self.stdout.write(f"  Total Documents: {stats['total_documents']}")
            self.stdout.write(f"  Projects: {stats['projects']}")
            self.stdout.write(f"  Tasks: {stats['tasks']}")
            self.stdout.write('='*60)
        
        self.stdout.write(self.style.SUCCESS('\n✅ RAG Initial Sync Complete!'))
        self.stdout.write(self.style.WARNING('\n💡 Tip: RAG will auto-sync new/updated projects and tasks via Django signals'))
