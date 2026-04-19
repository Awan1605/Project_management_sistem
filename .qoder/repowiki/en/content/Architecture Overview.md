# Architecture Overview

<cite>
**Referenced Files in This Document**
- [arviga/urls.py](file://arviga/urls.py)
- [arva/urls.py](file://arva/urls.py)
- [arva/views.py](file://arva/views.py)
- [arva/models.py](file://arva/models.py)
- [arva/middleware.py](file://arva/middleware.py)
- [arva/apps.py](file://arva/apps.py)
- [arva/forms.py](file://arva/forms.py)
- [arva/utils.py](file://arva/utils.py)
- [arva/ai_services.py](file://arva/ai_services.py)
- [arva/admin.py](file://arva/admin.py)
- [arva/templates/arva/base.html](file://arva/templates/arva/base.html)
- [arva/templatetags/arva_tags.py](file://arva/templatetags/arva_tags.py)
- [arviga/asgi.py](file://arviga/asgi.py)
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
10. [Appendices](#appendices)

## Introduction
This document describes the Arva Kanban system architecture built on Django. It explains how the system implements the Model-View-Controller (MVC) pattern, how URLs route requests to views, how middleware enforces policies, and how templates separate presentation from backend logic. It also documents integrations with external services (Google OAuth via allauth and Gemini AI), separation of concerns between frontend templates and backend logic, and infrastructure and scalability considerations.

## Project Structure
The project is organized into two primary packages:
- arviga: Django project configuration and ASGI entrypoint
- arva: The main application module containing models, views, URLs, templates, forms, middleware, and AI services

Key structural elements:
- URL routing is split between arviga (global) and arva (application routes)
- Templates are organized under arva/templates/arva with reusable partials
- Static assets (CSS/JS) are served via Django’s staticfiles mechanism
- Middleware enforces user activity tracking and maintenance mode
- AI services integrate with Google Gemini for priority analysis and chat assistance

```mermaid
graph TB
subgraph "arviga (Project Config)"
A1["arviga/urls.py<br/>Global URL patterns"]
A2["arviga/asgi.py<br/>ASGI entrypoint"]
end
subgraph "arva (Application)"
B1["arva/urls.py<br/>App URL patterns"]
B2["arva/views.py<br/>View handlers"]
B3["arva/models.py<br/>Domain models"]
B4["arva/middleware.py<br/>User activity & maintenance"]
B5["arva/forms.py<br/>Form definitions"]
B6["arva/utils.py<br/>Utilities"]
B7["arva/ai_services.py<br/>Gemini AI integration"]
B8["arva/admin.py<br/>Admin interface"]
B9["arva/templates/arva/base.html<br/>Base template"]
B10["arva/templatetags/arva_tags.py<br/>Template tags"]
end
A1 --> B1
A2 --> A1
B1 --> B2
B2 --> B3
B2 --> B5
B2 --> B6
B2 --> B7
B9 --> B10
```

**Diagram sources**
- [arviga/urls.py](file://arviga/urls.py#L1-L15)
- [arva/urls.py](file://arva/urls.py#L1-L98)
- [arva/views.py](file://arva/views.py#L1-L200)
- [arva/models.py](file://arva/models.py#L1-L120)
- [arva/middleware.py](file://arva/middleware.py#L1-L39)
- [arva/forms.py](file://arva/forms.py#L1-L120)
- [arva/utils.py](file://arva/utils.py#L1-L29)
- [arva/ai_services.py](file://arva/ai_services.py#L1-L120)
- [arva/admin.py](file://arva/admin.py#L1-L50)
- [arva/templates/arva/base.html](file://arva/templates/arva/base.html#L1-L60)
- [arva/templatetags/arva_tags.py](file://arva/templatetags/arva_tags.py#L1-L34)
- [arviga/asgi.py](file://arviga/asgi.py#L1-L6)

**Section sources**
- [arviga/urls.py](file://arviga/urls.py#L1-L15)
- [arva/urls.py](file://arva/urls.py#L1-L98)
- [arva/templates/arva/base.html](file://arva/templates/arva/base.html#L1-L60)

## Core Components
- Models: Define the domain entities (Project, Task, User, ActivityLog, etc.) and relationships. They encapsulate business rules and computed properties.
- Views: Handle HTTP requests, enforce permissions, orchestrate model operations, and render templates or JSON responses.
- Forms: Encapsulate validation and presentation logic for model-backed forms.
- Templates: Provide HTML rendering with Bootstrap and jQuery UI for responsive UI and drag-and-drop.
- Middleware: Enforce user activity tracking and maintenance mode.
- AI Services: Integrate with Google Gemini for priority analysis and chat assistance.
- Admin: Expose CRUD interfaces for models in Django admin.

**Section sources**
- [arva/models.py](file://arva/models.py#L100-L220)
- [arva/views.py](file://arva/views.py#L390-L470)
- [arva/forms.py](file://arva/forms.py#L135-L195)
- [arva/templates/arva/base.html](file://arva/templates/arva/base.html#L13-L25)
- [arva/middleware.py](file://arva/middleware.py#L7-L39)
- [arva/ai_services.py](file://arva/ai_services.py#L11-L22)
- [arva/admin.py](file://arva/admin.py#L8-L50)

## Architecture Overview
The system follows a layered MVC architecture:
- Model: Domain entities and business logic
- View: Request handlers that delegate to models and render templates or JSON
- Controller: Not a separate layer; views act as controllers by handling routing and orchestrating responses
- Template: Presentation layer with Bootstrap and jQuery UI
- Middleware: Cross-cutting concerns like user activity and maintenance mode
- External Integrations: Google OAuth (allauth) and Gemini AI

```mermaid
graph TB
Client["Browser"]
URL["arviga/urls.py<br/>Global patterns"]
AppURL["arva/urls.py<br/>App patterns"]
View["arva/views.py<br/>Handlers"]
Model["arva/models.py<br/>Entities & rules"]
Form["arva/forms.py<br/>Validation"]
Utils["arva/utils.py<br/>Helpers"]
AI["arva/ai_services.py<br/>Gemini integration"]
Temp["arva/templates/arva/base.html<br/>HTML templates"]
Tags["arva/templatetags/arva_tags.py<br/>Template tags"]
Client --> URL --> AppURL --> View
View --> Model
View --> Form
View --> Utils
View --> AI
View --> Temp
Temp --> Tags
```

**Diagram sources**
- [arviga/urls.py](file://arviga/urls.py#L6-L10)
- [arva/urls.py](file://arva/urls.py#L5-L97)
- [arva/views.py](file://arva/views.py#L1-L120)
- [arva/models.py](file://arva/models.py#L100-L220)
- [arva/forms.py](file://arva/forms.py#L135-L195)
- [arva/utils.py](file://arva/utils.py#L1-L29)
- [arva/ai_services.py](file://arva/ai_services.py#L11-L22)
- [arva/templates/arva/base.html](file://arva/templates/arva/base.html#L1-L60)
- [arva/templatetags/arva_tags.py](file://arva/templatetags/arva_tags.py#L1-L34)

## Detailed Component Analysis

### URL Routing System
- Global routing (arviga/urls.py) defines admin, app inclusion, and social accounts.
- Application routing (arva/urls.py) defines all Kanban endpoints including projects, tasks, comments, attachments, checklists, users, settings, and AI features.

```mermaid
sequenceDiagram
participant C as "Client"
participant G as "arviga/urls.py"
participant A as "arva/urls.py"
participant V as "arva/views.py"
C->>G : HTTP GET /
G->>A : include('arva.urls')
A->>V : Resolve pattern to view
V-->>C : Render template or JSON
```

**Diagram sources**
- [arviga/urls.py](file://arviga/urls.py#L6-L10)
- [arva/urls.py](file://arva/urls.py#L5-L97)

**Section sources**
- [arviga/urls.py](file://arviga/urls.py#L1-L15)
- [arva/urls.py](file://arva/urls.py#L1-L98)

### Middleware Configuration
- LastActivityMiddleware updates user activity timestamps periodically and persists them.
- MaintenanceModeMiddleware checks WebsiteSettings and renders maintenance.html for non-superusers.

```mermaid
flowchart TD
Start(["Request"]) --> CheckAuth["Is user authenticated?"]
CheckAuth --> |Yes| UpdateActivity["Update UserActivity in DB"]
CheckAuth --> |No| SkipActivity["Skip update"]
UpdateActivity --> LoadSettings["Load WebsiteSettings from cache/db"]
SkipActivity --> LoadSettings
LoadSettings --> CheckMaintenance{"Maintenance mode ON and user NOT superuser?"}
CheckMaintenance --> |Yes| RenderMaintenance["Render maintenance.html"]
CheckMaintenance --> |No| Continue["Continue to view"]
RenderMaintenance --> End(["Response"])
Continue --> End
```

**Diagram sources**
- [arva/middleware.py](file://arva/middleware.py#L7-L39)

**Section sources**
- [arva/middleware.py](file://arva/middleware.py#L1-L39)

### Data Models and Relationships
The models define the core domain:
- Project, SubProject, TaskList, Task, Label, Comment, Attachment, ChecklistItem, ActivityLog, UserProfile, UserActivity, WebsiteSettings, AIChatMessage
- Relationships and constraints are enforced via foreign keys and model-level validation.

```mermaid
erDiagram
USER {
int id PK
string username
string email
boolean is_active
datetime last_login
}
WEBSITESETTINGS {
int id PK
string site_name
string primary_color
string theme_mode
boolean maintenance_mode
}
USERPROFILE {
int id PK
int user_id FK
string avatar_icon
string theme_preference
string layout_preference
}
PROJECT {
int id PK
int owner_id FK
string name
boolean is_private
boolean is_project
boolean is_closed
string priority
int pm_assignee_id FK
date start_date
boolean start_date_tbd
date etd
}
SUBPROJECT {
int id PK
int project_id FK
string name
}
TASKLIST {
int id PK
int project_id FK
int sub_project_id FK
string name
int position
boolean is_archived
}
TASK {
int id PK
int project_id FK
int sub_project_id FK
int task_list_id FK
string title
string priority
string status
date due_date
boolean is_archived
}
LABEL {
int id PK
string name
string color
}
COMMENT {
int id PK
int task_id FK
int user_id FK
text content
}
ATTACHMENT {
int id PK
int task_id FK
string file
}
CHECKLISTITEM {
int id PK
int task_id FK
string content
boolean is_done
}
ACTIVITYLOG {
int id PK
int user_id FK
int project_id FK
int task_id FK
string action
text description
}
USER_ACTIVITY {
int id PK
int user_id FK
datetime last_activity
}
AI_CHAT_MESSAGE {
int id PK
int user_id FK
string role
text content
}
USER ||--o{ USERPROFILE : "has_one"
USER ||--o{ PROJECT : "owns"
USER ||--o{ COMMENT : "writes"
USER ||--o{ ACTIVITYLOG : "creates"
USER ||--o{ USER_ACTIVITY : "tracked_by"
USER ||--o{ AI_CHAT_MESSAGE : "author_of"
PROJECT ||--o{ SUBPROJECT : "contains"
PROJECT ||--o{ TASKLIST : "has_many"
PROJECT ||--o{ TASK : "contains"
PROJECT ||--o{ ACTIVITYLOG : "involved_in"
SUBPROJECT ||--o{ TASK : "contains"
TASKLIST ||--o{ TASK : "contains"
TASK ||--o{ COMMENT : "has_many"
TASK ||--o{ ATTACHMENT : "has_many"
TASK ||--o{ CHECKLISTITEM : "has_many"
TASK ||--o{ ACTIVITYLOG : "involved_in"
TASK ||--o{ LABEL : "tagged_with"
```

**Diagram sources**
- [arva/models.py](file://arva/models.py#L15-L445)

**Section sources**
- [arva/models.py](file://arva/models.py#L15-L445)

### Views and Controllers
Views handle:
- Authentication and authorization helpers
- Project and task CRUD operations
- Member management
- Comments, attachments, and checklists
- User settings and preferences
- AI priority queue and chat assistant
- JSON APIs for AJAX interactions

```mermaid
sequenceDiagram
participant U as "User"
participant V as "arva/views.py"
participant M as "arva/models.py"
participant F as "arva/forms.py"
participant T as "Templates"
U->>V : POST /project/create/
V->>F : Validate ProjectForm
F-->>V : Cleaned data
V->>M : Save Project + TaskLists
V->>M : Log Activity
V->>T : Render partial for DOM update
V-->>U : JSON {success, html, project_id}
```

**Diagram sources**
- [arva/views.py](file://arva/views.py#L477-L500)
- [arva/forms.py](file://arva/forms.py#L135-L195)
- [arva/models.py](file://arva/models.py#L101-L127)

**Section sources**
- [arva/views.py](file://arva/views.py#L394-L526)
- [arva/forms.py](file://arva/forms.py#L135-L195)
- [arva/models.py](file://arva/models.py#L101-L127)

### AI Integration (Gemini)
The AI services module integrates with Google Gemini:
- Priority analysis: Builds task context, constructs prompts, and parses JSON responses
- Chat assistant: Provides contextual recommendations and maintains conversation history
- Factory functions return configured service instances

```mermaid
classDiagram
class GeminiService {
+analyze_task(task) Dict
+analyze_multiple_tasks(tasks) Dict[]
+get_priority_queue(user, project, limit) Dict[]
}
class AIChatService {
+chat(user, message, history) str
+get_work_recommendation(user) str
}
class AIChatMessage {
+user User
+role str
+content text
+context_tasks JSON
}
GeminiService --> AIChatMessage : "stores analysis logs"
AIChatService --> AIChatMessage : "stores chat logs"
```

**Diagram sources**
- [arva/ai_services.py](file://arva/ai_services.py#L11-L22)
- [arva/ai_services.py](file://arva/ai_services.py#L196-L207)
- [arva/models.py](file://arva/models.py#L430-L445)

**Section sources**
- [arva/ai_services.py](file://arva/ai_services.py#L11-L22)
- [arva/ai_services.py](file://arva/ai_services.py#L196-L207)
- [arva/models.py](file://arva/models.py#L430-L445)

### Frontend Separation and Responsive Design
- Base template loads Bootstrap and jQuery UI for responsive layout and drag-and-drop.
- Template tags compute effective theme and layout preferences.
- Static assets are served via Django’s staticfiles.

```mermaid
flowchart TD
TPL["arva/templates/arva/base.html"] --> CSS["Bootstrap + jQuery UI"]
TPL --> TAGS["arva/templatetags/arva_tags.py"]
TAGS --> Theme["Effective theme/layout"]
CSS --> UI["Responsive UI"]
```

**Diagram sources**
- [arva/templates/arva/base.html](file://arva/templates/arva/base.html#L13-L25)
- [arva/templatetags/arva_tags.py](file://arva/templatetags/arva_tags.py#L6-L27)

**Section sources**
- [arva/templates/arva/base.html](file://arva/templates/arva/base.html#L1-L60)
- [arva/templatetags/arva_tags.py](file://arva/templatetags/arva_tags.py#L1-L34)

## Dependency Analysis
- arviga/urls.py depends on arva/urls.py and allauth URLs for authentication.
- arva/views.py depends on models, forms, utils, and ai_services.
- arva/middleware.py depends on models and cache.
- arva/templates depend on templatetags and static assets.
- External dependencies: allauth for OAuth, google genai SDK for Gemini.

```mermaid
graph LR
G["arviga/urls.py"] --> A["arva/urls.py"]
A --> V["arva/views.py"]
V --> M["arva/models.py"]
V --> F["arva/forms.py"]
V --> U["arva/utils.py"]
V --> AI["arva/ai_services.py"]
V --> T["arva/templates/*"]
T --> TT["arva/templatetags/*"]
MW["arva/middleware.py"] --> M
MW --> T
A --> OA["allauth URLs"]
AI --> GG["google genai SDK"]
```

**Diagram sources**
- [arviga/urls.py](file://arviga/urls.py#L6-L10)
- [arva/urls.py](file://arva/urls.py#L1-L10)
- [arva/views.py](file://arva/views.py#L1-L32)
- [arva/middleware.py](file://arva/middleware.py#L1-L6)
- [arva/ai_services.py](file://arva/ai_services.py#L6-L8)

**Section sources**
- [arviga/urls.py](file://arviga/urls.py#L1-L15)
- [arva/urls.py](file://arva/urls.py#L1-L10)
- [arva/views.py](file://arva/views.py#L1-L32)
- [arva/middleware.py](file://arva/middleware.py#L1-L6)
- [arva/ai_services.py](file://arva/ai_services.py#L6-L8)

## Performance Considerations
- Database queries: Views use select_related and prefetch_related to minimize N+1 queries.
- Pagination: Views implement pagination for large datasets.
- Middleware caching: WebsiteSettings cached to reduce DB hits.
- Asynchronous email: EmailThread runs in background to avoid blocking requests.
- Static assets: Bootstrap and jQuery UI loaded from CDN/static bundles.

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
Common areas to inspect:
- Authentication failures: Verify allauth URLs and login/logout views.
- Permission errors: Review require_role and get_role helpers in views.
- Maintenance mode: Confirm WebsiteSettings maintenance flag and user permissions.
- AI integration: Ensure GEMINI_API_KEY is configured and GeminiService initialization succeeds.
- Email delivery: Check EmailThread usage and mail server configuration.

**Section sources**
- [arva/views.py](file://arva/views.py#L98-L104)
- [arva/middleware.py](file://arva/middleware.py#L24-L39)
- [arva/ai_services.py](file://arva/ai_services.py#L14-L21)
- [arva/utils.py](file://arva/utils.py#L11-L28)

## Conclusion
Arva Kanban implements a clean Django MVC architecture with clear separation of concerns. URL routing is centralized in arviga and delegated to arva for application-specific endpoints. Middleware enforces cross-cutting policies, while templates and template tags handle presentation. Integrations with Google OAuth and Gemini AI enhance functionality without compromising modularity. The system balances rapid development with maintainable structure and offers scalable patterns for future growth.

[No sources needed since this section summarizes without analyzing specific files]

## Appendices

### Deployment Topology
- ASGI entrypoint configured in arviga/asgi.py
- Static files served during DEBUG; production should serve via web server or CDN
- Environment variables required: GEMINI_API_KEY for AI features

**Section sources**
- [arviga/asgi.py](file://arviga/asgi.py#L1-L6)
- [arva/ai_services.py](file://arva/ai_services.py#L14-L21)