# Project Overview

<cite>
**Referenced Files in This Document**
- [README.txt](file://README.txt)
- [SETUP_GUIDE.md](file://SETUP_GUIDE.md)
- [models.py](file://arva/models.py)
- [views.py](file://arva/views.py)
- [urls.py](file://arva/urls.py)
- [ai_services.py](file://arva/ai_services.py)
- [project_detail.html](file://arva/templates/arva/project_detail.html)
- [_task_board.html](file://arva/templates/arva/_task_board.html)
- [ai_priority_queue.html](file://arva/templates/arva/ai_priority_queue.html)
- [ai_chat.html](file://arva/templates/arva/ai_chat.html)
- [arva.js](file://static/arva/js/arva.js)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)

## Introduction
Arva Kanban is a Trello-like kanban board system designed for project and task management. It enables teams to organize work into boards, lists, and cards, supporting drag-and-drop operations, role-based access control, and AI-powered insights. The platform emphasizes real-time collaboration, structured workflows, and intelligent prioritization to improve team productivity.

Key capabilities include:
- Kanban board with lists and cards, drag-and-drop reordering, and dual view modes (card and list)
- Role-based access control with flexible sharing policies
- AI integration for priority analysis and conversational task assistance
- Rich task features: comments, attachments, checklists, labels, and due dates
- AJAX-driven interactions for seamless user experience

## Project Structure
The project follows a Django-based backend with a modern frontend leveraging Bootstrap and jQuery UI for drag-and-drop. Templates are organized under arva/templates/arva, and static assets are served via static/arva.

```mermaid
graph TB
subgraph "Backend (Django)"
V["Views<br/>arva/views.py"]
U["URLs<br/>arva/urls.py"]
M["Models<br/>arva/models.py"]
A["AI Services<br/>arva/ai_services.py"]
end
subgraph "Frontend"
TPL["Templates<br/>arva/templates/arva/*.html"]
JS["JavaScript<br/>static/arva/js/arva.js"]
CSS["CSS<br/>static/arva/css/*.css"]
BOOT["Bootstrap<br/>static/css/bootstrap-*.css"]
JQUI["jQuery UI<br/>static/js/jquery-ui-*.js"]
end
V --> U
V --> M
V --> A
TPL --> JS
JS --> BOOT
JS --> JQUI
CSS --> BOOT
```

**Diagram sources**
- [views.py](file://arva/views.py#L1-L120)
- [urls.py](file://arva/urls.py#L1-L98)
- [models.py](file://arva/models.py#L101-L315)
- [ai_services.py](file://arva/ai_services.py#L11-L326)
- [arva.js](file://static/arva/js/arva.js#L105-L1599)

**Section sources**
- [README.txt](file://README.txt#L1-L35)
- [SETUP_GUIDE.md](file://SETUP_GUIDE.md#L1-L95)

## Core Components
- Project: Top-level container for tasks, with optional private sharing and project metadata (start date, ETD, priority).
- SubProject: Hierarchical subdivision within a project for scoped task management.
- TaskList: Columns on the kanban board representing workflow stages (e.g., To Do, In Progress, Done).
- Task: Individual work items with priority, status, due dates, assignees, labels, and AI-enhanced fields.
- ActivityLog: Audit trail for all major actions performed on projects and tasks.
- AI Services: Gemini-powered priority analysis and chat assistant for contextual task guidance.

These components collectively enable structured workflows, visibility, and intelligent insights.

**Section sources**
- [models.py](file://arva/models.py#L101-L315)
- [models.py](file://arva/models.py#L387-L445)
- [ai_services.py](file://arva/ai_services.py#L11-L326)

## Architecture Overview
Arva Kanban uses a layered architecture:
- Presentation Layer: Django templates render the board UI, filters, and modals.
- Business Logic Layer: Views orchestrate requests, enforce access control, and coordinate model operations.
- Data Access Layer: Models define entities and relationships; AI services integrate external APIs.
- Frontend Interaction Layer: jQuery UI powers drag-and-drop; Bootstrap provides responsive UI; custom JavaScript handles AJAX and dynamic updates.

```mermaid
sequenceDiagram
participant User as "User"
participant Browser as "Browser"
participant JS as "arva.js"
participant Django as "Django Views"
participant Models as "Django Models"
participant AI as "Gemini AI"
User->>Browser : Open project detail
Browser->>JS : Initialize board and listeners
JS->>Django : Fetch project data (AJAX)
Django->>Models : Query tasks, lists, activities
Models-->>Django : Serialized data
Django-->>JS : JSON payload
JS-->>Browser : Render board and cards
User->>JS : Drag-and-drop card
JS->>Django : POST move/reorder
Django->>Models : Update positions
Models-->>Django : Success
Django-->>JS : JSON success
JS-->>Browser : Update DOM without reload
User->>JS : Click AI Priority Queue
JS->>Django : POST refresh analysis
Django->>AI : Analyze tasks
AI-->>Django : Priority recommendations
Django-->>JS : JSON results
JS-->>Browser : Update priority table
```

**Diagram sources**
- [project_detail.html](file://arva/templates/arva/project_detail.html#L239-L241)
- [_task_board.html](file://arva/templates/arva/_task_board.html#L1-L114)
- [arva.js](file://static/arva/js/arva.js#L105-L1599)
- [views.py](file://arva/views.py#L713-L805)
- [ai_services.py](file://arva/ai_services.py#L115-L165)

## Detailed Component Analysis

### Kanban Board and Views
The board renders lists and cards, supports dual view modes (card/list), and integrates filtering and sorting. Drag-and-drop is handled by jQuery UI, while AJAX updates maintain responsiveness.

```mermaid
flowchart TD
Start(["Load Project Detail"]) --> RenderBoard["Render Board Template<br/>_task_board.html"]
RenderBoard --> InitView["Initialize View Mode<br/>localStorage + Toggle Buttons"]
InitView --> BindEvents["Bind Event Listeners<br/>arva.js"]
BindEvents --> DragDrop["Drag-and-Drop Cards<br/>jQuery UI"]
DragDrop --> AjaxMove["AJAX Move/Reorder<br/>POST /task/<id>/move/"]
AjaxMove --> UpdateDOM["Update DOM Without Reload"]
UpdateDOM --> End(["Board Updated"])
```

**Diagram sources**
- [_task_board.html](file://arva/templates/arva/_task_board.html#L1-L114)
- [arva.js](file://static/arva/js/arva.js#L105-L1599)
- [views.py](file://arva/views.py#L713-L805)

**Section sources**
- [project_detail.html](file://arva/templates/arva/project_detail.html#L1-L581)
- [_task_board.html](file://arva/templates/arva/_task_board.html#L1-L176)
- [arva.js](file://static/arva/js/arva.js#L105-L1599)

### Role-Based Access Control
Access control is enforced at the project level. While explicit role tokens exist, the system treats project-access users uniformly for most endpoints, with owner-only restrictions for administrative actions.

```mermaid
flowchart TD
Request["Incoming Request"] --> CheckView["Check Project.can_user_view(user)"]
CheckView --> |Denied| Forbidden["HTTP 403 Forbidden"]
CheckView --> |Allowed| Gate["Gatekeeper Logic<br/>require_role()"]
Gate --> |Admin Required| OwnerCheck["Is Owner?"]
OwnerCheck --> |Yes| Allow["Allow Action"]
OwnerCheck --> |No| Forbidden
Gate --> |Any Access| Allow
```

**Diagram sources**
- [models.py](file://arva/models.py#L146-L159)
- [views.py](file://arva/views.py#L91-L105)

**Section sources**
- [models.py](file://arva/models.py#L146-L159)
- [views.py](file://arva/views.py#L91-L105)

### AI Integration: Priority Analysis and Chat Assistant
AI services leverage Google Gemini to analyze tasks and provide priority recommendations and conversational guidance.

```mermaid
sequenceDiagram
participant User as "User"
participant UI as "AI Priority Queue Page"
participant JS as "arva.js"
participant Django as "Django Views"
participant AI as "GeminiService"
User->>UI : Click "Refresh Analysis"
UI->>JS : Trigger refreshAnalysis()
JS->>Django : POST /ai/priority-refresh/
Django->>AI : Analyze multiple tasks
AI-->>Django : Priority recommendations
Django-->>JS : JSON results
JS-->>UI : Update priority table
```

**Diagram sources**
- [ai_priority_queue.html](file://arva/templates/arva/ai_priority_queue.html#L673-L773)
- [ai_services.py](file://arva/ai_services.py#L115-L165)
- [views.py](file://arva/views.py#L1-L120)

**Section sources**
- [ai_services.py](file://arva/ai_services.py#L11-L326)
- [ai_priority_queue.html](file://arva/templates/arva/ai_priority_queue.html#L1-L804)
- [ai_chat.html](file://arva/templates/arva/ai_chat.html#L1-L912)

### Data Models Overview
The core data model defines projects, subprojects, task lists, tasks, and related entities.

```mermaid
erDiagram
PROJECT {
int id PK
varchar name
text description
boolean is_private
boolean is_project
boolean is_closed
enum priority
date start_date
boolean start_date_tbd
date etd
datetime created_at
}
SUBPROJECT {
int id PK
int project_id FK
varchar name
text description
datetime created_at
}
TASKLIST {
int id PK
int project_id FK
int sub_project_id FK
varchar name
int position
boolean is_archived
datetime created_at
}
TASK {
int id PK
int project_id FK
int sub_project_id FK
int task_list_id FK
varchar title
text description
int order
enum priority
enum status
date start_date
boolean start_date_tbd
date due_date
int ai_priority_score
text ai_priority_reason
varchar ai_complexity
int ai_estimated_hours
datetime ai_analyzed_at
boolean is_archived
datetime created_at
datetime updated_at
}
ACTIVITYLOG {
int id PK
int user_id FK
int project_id FK
int task_id FK
enum action
text description
datetime created_at
}
PROJECT ||--o{ SUBPROJECT : "contains"
PROJECT ||--o{ TASKLIST : "contains"
SUBPROJECT ||--o{ TASKLIST : "contains"
TASKLIST ||--o{ TASK : "contains"
PROJECT ||--o{ ACTIVITYLOG : "generates"
TASK ||--o{ ACTIVITYLOG : "generates"
```

**Diagram sources**
- [models.py](file://arva/models.py#L101-L315)
- [models.py](file://arva/models.py#L387-L445)

**Section sources**
- [models.py](file://arva/models.py#L101-L315)
- [models.py](file://arva/models.py#L387-L445)

## Dependency Analysis
- Backend dependencies: Django ORM, Google AI SDK (Gemini), and standard libraries.
- Frontend dependencies: Bootstrap for UI, jQuery UI for drag-and-drop, SweetAlert2 for UX feedback.
- Template dependencies: Django template tags and static asset inclusion.

```mermaid
graph LR
Django["Django Views<br/>arva/views.py"] --> Models["Models<br/>arva/models.py"]
Django --> URLs["URLs<br/>arva/urls.py"]
Django --> AIServices["AI Services<br/>arva/ai_services.py"]
Templates["Templates<br/>arva/templates/arva/*.html"] --> JS["arva.js"]
JS --> Bootstrap["Bootstrap CSS/JS"]
JS --> JQUI["jQuery UI CSS/JS"]
JS --> SweetAlert["SweetAlert2"]
```

**Diagram sources**
- [views.py](file://arva/views.py#L1-L120)
- [urls.py](file://arva/urls.py#L1-L98)
- [models.py](file://arva/models.py#L101-L315)
- [ai_services.py](file://arva/ai_services.py#L11-L326)
- [arva.js](file://static/arva/js/arva.js#L105-L1599)

**Section sources**
- [urls.py](file://arva/urls.py#L1-L98)
- [SETUP_GUIDE.md](file://SETUP_GUIDE.md#L1-L95)

## Performance Considerations
- Efficient queries: Views use select_related and prefetch_related to minimize N+1 queries when rendering boards and lists.
- Pagination: Task lists support configurable pagination to reduce DOM size and improve responsiveness.
- Client-side caching: LocalStorage persists view preferences and filters to avoid repeated computations.
- Minimal DOM updates: AJAX endpoints return partial HTML or JSON, enabling targeted UI updates without full page reloads.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common issues and resolutions:
- Database connectivity: Verify MySQL configuration and credentials; test connection using provided commands.
- Duplicate migration columns: Fake migration rollback if encountering duplicate column errors.
- Switching databases: Use local settings override to switch to SQLite for development.
- AI API configuration: Ensure GEMINI_API_KEY is configured; verify model availability and quotas.

**Section sources**
- [SETUP_GUIDE.md](file://SETUP_GUIDE.md#L42-L83)

## Conclusion
Arva Kanban delivers a robust, extensible kanban solution tailored for team collaboration. Its combination of drag-and-drop boards, structured workflows, role-based access, and AI-driven insights makes it suitable for diverse use cases—from agile project management to daily task tracking and workflow optimization. The modular Django architecture and responsive frontend ensure scalability and maintainability for growing teams.