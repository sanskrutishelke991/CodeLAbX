# CodeLabX - Architecture Document

## System Overview

CodeLabX is a monolithic Django web application designed for scalability while maintaining simplicity for MVP development. The architecture follows Django's Model-View-Template (MVT) pattern with clear separation of concerns.

## Technology Stack

### Backend
- **Framework**: Django 4.x
- **Language**: Python 3.8+
- **Database**: SQLite (MVP), PostgreSQL (future)
- **Authentication**: Django's built-in authentication system
- **ORM**: Django ORM

### Frontend
- **Templates**: Django Templates
- **CSS Framework**: Bootstrap 5
- **JavaScript**: Vanilla JS (minimal)
- **Icons**: Bootstrap Icons or FontAwesome

### Development Tools
- **Version Control**: Git
- **Package Management**: pip + requirements.txt
- **Static Files**: Django's staticfiles app
- **Media Files**: Django's media handling

## Django Apps Structure

### Core Apps

#### 1. `users` - User Management
**Purpose**: Handle user authentication, profiles, and preferences

**Key Components**:
- Models: User, UserProfile, UserPreferences
- Views: Registration, Login, Profile Update, Settings
- Templates: Auth forms, profile pages
- Services: User creation, preference management

**Responsibilities**:
- User registration and authentication
- Profile information storage
- Learning preferences (topic, duration, hours)
- Activity tracking integration

#### 2. `roadmaps` - Learning Path Generation
**Purpose**: Generate and manage personalized learning roadmaps

**Key Components**:
- Models: Roadmap, Day, Topic, Module
- Views: Roadmap creation, display, navigation
- Templates: Roadmap overview, daily view
- Services: Roadmap generation algorithm

**Responsibilities**:
- Generate day-by-day learning schedules
- Map topics to time allocations
- Handle roadmap modifications
- Track progress through roadmap

#### 3. `content` - Educational Content Management
**Purpose**: Store and deliver educational content

**Key Components**:
- Models: TheoryContent, VisualContent, PracticeTask, Project
- Views: Content display, search, filtering
- Templates: Content pages, visual explanations
- Services: Content retrieval, formatting

**Responsibilities**:
- Store theory text and explanations
- Manage visual content (images, diagrams)
- Provide practice tasks and solutions
- Handle project descriptions and guidelines

#### 4. `assessments` - Quizzes and Tests
**Purpose**: Create and administer assessments

**Key Components**:
- Models: Quiz, Question, Answer, UserAttempt, Result
- Views: Quiz taking, result display, analytics
- Templates: Quiz interface, results page
- Services: Quiz scoring, performance tracking

**Responsibilities**:
- Create quiz questions
- Administer tests to users
- Score and store results
- Provide performance analytics

#### 5. `progress` - Progress Tracking
**Purpose**: Track and visualize user progress

**Key Components**:
- Models: ActivityLog, Progress, Achievement
- Views: Dashboard, heatmap display, statistics
- Templates: Dashboard, progress charts
- Services: Activity logging, progress calculation

**Responsibilities**:
- Log user activities
- Generate GitHub-style heatmaps
- Calculate completion percentages
- Track achievements

#### . `admin` - Django Admin (Built-in)
**Purpose**: Administrative interface for content management

**Customization**:
- Custom admin interfaces for eachapp
- Bulk content upload
- User management
- Analytics dashboard

## Data Flow Architecture

### User Registration Flow
```
User → Registration Form → users.views.register → 
users.models.UserProfile creation → 
users.models.UserPreferences creation → 
Redirect to Dashboard
```

### Roadmap Generation Flow
```
User → Input Form (topic, duration, hours) → 
roadmaps.services.generate_roadmap → 
Algorithm distributes topics across days → 
roadmaps.models.Roadmap creation → 
roadmaps.models.Day creation (linked to content) → 
Display Roadmap
```

### Daily Learning Flow
```
User → Select Day from Roadmap → 
roadmaps.views.day_detail → 
Retrieve content.models.TheoryContent →  
Retrieve content.models.VisualContent → 
Retrieve content.models.PracticeTask → 
Render combined view → 
Log activity to progress.models.ActivityLog
```

### Assessment Flow
```
User → Start Quiz → 
assessments.views.take_quiz → 
Display questions → 
Submit answers → 
assessments.services.score_quiz → 
Store assessments.models.UserAttempt → 
Display results → 
Update progress.models.Progress
```

### Progress Tracking Flow
```
User Action (complete task, view content) → 
progress.services.log_activity → 
progress.models.ActivityLog creation → 
progress.services.calculate_progress → 
Update progress.models.Progress → 
Generate heatmap data
```

## Service Layer Architecture

### Roadmap Generation Service
**Location**: `roadmaps/services.py`

**Key Functions**:
- `generate_roadmap(user, topic, duration, daily_hours)`: Main generation logic
- `distribute_content(topic, total_days)`: Distribute topics across days
- `calculate_time_allocation(content, daily_hours)`: Time estimation per task
- `create_roadmap_structure(roadmap_data)`: Create database records

### Content Management Service
**Location**: `content/services.py`

**Key Functions**:
- `get_content_for_day(day_id)`: Retrieve all content for a specific day
- `format_theory_content(content)`: Format text for display
- `get_visual_explanations(topic)`: Retrieve relevant visual content
- `search_content(query)`: Content search functionality

### Assessment Service
**Location**: `assessments/services.py`

**Key Functions**:
- `create_quiz(topic, difficulty)`: Generate quiz from question bank
- `score_attempt(attempt_id)`: Calculate quiz score
- `get_user_performance(user_id)`: Aggregate performance data
- `recommend_next_topic(user_id)`: Suggest next learning area

### Progress Tracking Service
**Location**: `progress/services.py`

**Key Functions**:
- `log_activity(user, activity_type, metadata)`: Record user actions
- `calculate_completion_percentage(user, roadmap)`: Progress calculation
- `generate_heatmap_data(user_id)`: Generate GitHub-style heatmap data
- `get_achievements(user_id)`: Retrieve user achievements

## Integration Points

### Internal Integrations

#### User ↔ Roadmap
- User preferences drive roadmap generation
- Roadmap progress updates user profile

#### Roadmap ↔ Content
- Roadmap days reference specific content items
- Content metadata used for roadmap time estimation

#### Content ↔ Assessments
- Quizzes linked to specific content modules
- Assessment results influence content recommendations

#### All Apps ↔ Progress
- Every user action logged to progress service
- Progress data used across all views for personalization

### External Integrations (Future)

#### API Layer (Phase 2)
- REST API endpoints using Django REST Framework
- Authentication via JWT tokens
- Rate limiting and API key management

#### AI Services (Phase 2)
- Integration with OpenAI API for personalized recommendations
- Content generation assistance
- Chatbot for doubt resolution

#### Third-party Auth (Phase 3)
- Google OAuth integration
- GitHub OAuth integration
- Social login options

#### Email Services (Phase 2)
- SendGrid or AWS SES for email notifications
- Progress reports
- Reminder emails

#### Analytics (Phase 2)
- Google Analytics integration
- Custom event tracking
- User behavior analysis

## Database Architecture

### Database Strategy
- **MVP**: Single SQLite database
- **Future**: PostgreSQL with read replicas for scaling
- **Migration Path**: Django's migration system supports seamless switch

### Connection Pooling
- **MVP**: Django's default connection handling
- **Future**: Connection pooling with PgBouncer for PostgreSQL

### Caching Strategy
- **MVP**: No caching (simple SQLite)
- **Future**: Redis caching for:
  - Roadmap generation results
  - Content rendering
  - User session data
  - Heatmap calculations

## Static and Media Files

### Static Files
- **Location**: `static/` directory in each app
- **Management**: Django's collectstatic command
- **CDN**: Whitenoise for development, CloudFront for production

### Media Files
- **Location**: `media/` directory
- **Types**: User uploads, visual content images
- **Storage**: Local filesystem (MVP), S3 (future)

## Security Architecture

### Authentication
- Django's built-in authentication
- Password hashing with PBKDF2
- Session-based authentication
- Future: JWT token support for APIs

### Authorization
- Django's permission system
- Custom permissions for content access
- Role-based access control for admin

### Security Middleware
- CSRF protection
- XSS protection via Django templates
- SQL injection prevention via ORM
- Secure headers (CSP, HSTS)

### Data Protection
- User data encryption at rest (future)
- HTTPS enforcement
- Secure cookie flags

## Deployment Architecture

### Development Environment
- Local Django development server
- SQLite database
- Debug mode enabled

### Production Environment (MVP)
- Gunicorn as WSGI server
- Nginx as reverse proxy
- SQLite database (can migrate to PostgreSQL)
- Static files served via Whitenoise

### Production Environment (Future)
- Containerized deployment with Docker
- Kubernetes for orchestration
- PostgreSQL database
- Redis for caching
- CDN for static assets
- Load balancer for horizontal scaling

## Scalability Considerations

### Vertical Scaling (MVP)
- Single server deployment
- Database optimization
- Query optimization
- Caching strategies

### Horizontal Scaling (Future)
- Stateless application design
- Database read replicas
- Microservice extraction (if needed)
- Load balancing

### Performance Optimization
- Database indexing
- Query optimization
- Lazy loading for content
- Pagination for large datasets
- Asynchronous task processing (Celery)

## Monitoring and Logging

### Logging Strategy
- Django's built-in logging
- Application logs: user actions, errors
- Database query logging (development)
- Future: ELK stack integration

### Monitoring
- Application performance monitoring
- Error tracking (Sentry integration)
- Database performance monitoring
- User activity analytics

## Testing Strategy

### Unit Tests
- Model tests
- Service layer tests
- Utility function tests

### Integration Tests
- View tests
- End-to-end user flows
- Database integration

### Future Testing
- API testing
- Load testing
- Security testing

## Development Workflow

### Git Workflow
- Feature branch workflow
- Pull request reviews
- CI/CD pipeline (future)

### Code Organization
- Each app is self-contained
- Shared utilities in `core/` app
- Clear separation of models, views, templates
- Service layer for business logic

## Documentation

### Code Documentation
- Docstrings for all functions
- Type hints for Python 3.8+
- Inline comments for complex logic

### API Documentation (Future)
- OpenAPI/Swagger specification
- API usage examples
- Authentication documentation

## Future Architecture Evolution

### Phase 2: API Layer
- Extract API endpoints to separate app
- Implement REST API with DRF
- Add API versioning
- Implement rate limiting

### Phase 3: Microservices (If Needed)
- Extract content service
- Extract assessment service
- Extract progress tracking service
- Event-driven architecture with message queue

### Phase 4: Mobile Backend
- GraphQL API for mobile apps
- Offline sync support
- Push notification service
