# CodeLabX - Database Schema

## Database Overview

CodeLabX uses a relational database schema designed for Django ORM. The schema is organized by Django apps with clear relationships between models.

**Database**: SQLite (MVP), PostgreSQL (future)

## Schema by App

### users App

#### User (Extended Django User)
Extends Django's built-in User model with additional fields.

**Fields**:
- `id` (PK, AutoField)
- `username` (CharField, unique)
- `email` (EmailField, unique)
- `password` (CharField, hashed)
- `first_name` (CharField)
- `last_name` (CharField)
- `is_active` (BooleanField)
- `date_joined` (DateTimeField, auto_now_add)
- `last_login` (DateTimeField)

**Indexes**:
- `idx_username` on username
- `idx_email` on email

#### UserProfile
One-to-one relationship with User model.

**Fields**:
- `id` (PK, AutoField)
- `user` (OneToOneField to User, related_name='profile')
- `bio` (TextField, blank=True)
- `avatar` (ImageField, upload_to='avatars/', blank=True)
- `date_of_birth` (DateField, null=True, blank=True)
- `location` (CharField, max_length=100, blank=True)
- `created_at` (DateTimeField, auto_now_add)
- `updated_at` (DateTimeField, auto_now=True)

**Indexes**:
- `idx_user` on user

#### UserPreferences
Stores user learning preferences.

**Fields**:
- `id` (PK, AutoField)
- `user` (OneToOneField to User, related_name='preferences')
- `preferred_topic` (CharField, choices=TOPIC_CHOICES)
- `learning_duration_months` (PositiveIntegerField)
- `daily_study_hours` (PositiveDecimalField, max_digits=3, decimal_places=1)
- `difficulty_level` (CharField, choices=DIFFICULTY_CHOICES)
- `notification_enabled` (BooleanField, default=True)
- `created_at` (DateTimeField, auto_now_add)
- `updated_at` (DateTimeField, auto_now=True)

**Choices**:
- `TOPIC_CHOICES`: [('ML', 'Machine Learning'), ('AI', 'Artificial Intelligence'), ('DS', 'Data Science'), ('DSA', 'Data Structures & Algorithms')]
- `DIFFICULTY_CHOICES`: [('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')]

**Indexes**:
- `idx_user` on user
- `idx_topic` on preferred_topic

### roadmaps App

#### Roadmap
Represents a complete learning path for a user.

**Fields**:
- `id` (PK, AutoField)
- `user` (ForeignKey to User, related_name='roadmaps')
- `topic` (CharField, choices=TOPIC_CHOICES)
- `title` (CharField, max_length=200)
- `description` (TextField, blank=True)
- `total_days` (PositiveIntegerField)
- `daily_hours` (PositiveDecimalField, max_digits=3, decimal_places=1)
- `status` (CharField, choices=STATUS_CHOICES, default='active')
- `start_date` (DateField)
- `end_date` (DateField)
- `created_at` (DateTimeField, auto_now_add)
- `updated_at` (DateTimeField, auto_now=True)

**Choices**:
- `STATUS_CHOICES`: [('active', 'Active'), ('completed', 'Completed'), ('paused', 'Paused'), ('archived', 'Archived')]

**Indexes**:
- `idx_user` on user
- `idx_topic` on topic
- `idx_status` on status
- `idx_dates` on (start_date, end_date)

#### Day
Represents a single day in a roadmap.

**Fields**:
- `id` (PK, AutoField)
- `roadmap` (ForeignKey to Roadmap, related_name='days')
- `day_number` (PositiveIntegerField)
- `title` (CharField, max_length=200)
- `description` (TextField, blank=True)
- `estimated_hours` (PositiveDecimalField, max_digits=3, decimal_places=1)
- `is_completed` (BooleanField, default=False)
- `completed_at` (DateTimeField, null=True, blank=True)
- `order` (PositiveIntegerField)

**Indexes**:
- `idx_roadmap` on roadmap
- `idx_day_number` on day_number
- `idx_order` on order
- `idx_completed` on is_completed

**Unique Constraint**:
- `unique_roadmap_day` on (roadmap, day_number)

#### Module
Represents a learning module within a day.

**Fields**:
- `id` (PK, AutoField)
- `day` (ForeignKey to Day, related_name='modules')
- `title` (CharField, max_length=200)
- `module_type` (CharField, choices=MODULE_TYPE_CHOICES)
- `order` (PositiveIntegerField)
- `estimated_minutes` (PositiveIntegerField)

**Choices**:
- `MODULE_TYPE_CHOICES`: [('theory', 'Theory'), ('visual', 'Visual Explanation'), ('practice', 'Practice Task'), ('project', 'Project'), ('quiz', 'Quiz')]

**Indexes**:
- `idx_day` on day
- `idx_type` on module_type
- `idx_order` on order

### content App

#### Topic
Master table for available topics.

**Fields**:
- `id` (PK, AutoField)
- `name` (CharField, max_length=100, unique=True)
- `slug` (SlugField, unique=True)
- `description` (TextField)
- `icon` (CharField, max_length=50, blank=True)
- `color` (CharField, max_length=7, blank=True)  # Hex color
- `is_active` (BooleanField, default=True)
- `created_at` (DateTimeField, auto_now_add)

**Indexes**:
- `idx_slug` on slug
- `idx_active` on is_active

#### TheoryContent
Educational theory content.

**Fields**:
- `id` (PK, AutoField)
- `topic` (ForeignKey to Topic, related_name='theory_content')
- `title` (CharField, max_length=200)
- `content` (TextField)
- `summary` (TextField, blank=True)
- `difficulty_level` (CharField, choices=DIFFICULTY_CHOICES)
- `estimated_reading_minutes` (PositiveIntegerField)
- `order` (PositiveIntegerField)
- `is_published` (BooleanField, default=True)
- `created_at` (DateTimeField, auto_now_add)
- `updated_at` (DateTimeField, auto_now=True)

**Indexes**:
- `idx_topic` on topic
- `idx_difficulty` on difficulty_level
- `idx_published` on is_published
- `idx_order` on order

#### VisualContent
Visual explanations (diagrams, charts, images).

**Fields**:
- `id` (PK, AutoField)
- `topic` (ForeignKey to Topic, related_name='visual_content')
- `title` (CharField, max_length=200)
- `description` (TextField, blank=True)
- `image` (ImageField, upload_to='visual_content/')
- `image_url` (URLField, blank=True)
- `caption` (TextField, blank=True)
- `visual_type` (CharField, choices=VISUAL_TYPE_CHOICES)
- `related_theory` (ForeignKey to TheoryContent, related_name='visuals', null=True, blank=True)
- `order` (PositiveIntegerField)
- `is_published` (BooleanField, default=True)
- `created_at` (DateTimeField, auto_now_add)

**Choices**:
- `VISUAL_TYPE_CHOICES`: [('diagram', 'Diagram'), ('chart', 'Chart'), ('infographic', 'Infographic'), ('screenshot', 'Screenshot'), ('illustration', 'Illustration')]

**Indexes**:
- `idx_topic` on topic
- `idx_type` on visual_type
- `idx_theory` on related_theory
- `idx_published` on is_published

#### PracticeTask
Practice exercises and coding tasks.

**Fields**:
- `id` (PK, AutoField)
- `topic` (ForeignKey to Topic, related_name='practice_tasks')
- `title` (CharField, max_length=200)
- `description` (TextField)
- `instructions` (TextField)
- `starter_code` (TextField, blank=True)
- `solution_code` (TextField, blank=True)
- `hints` (TextField, blank=True)
- `difficulty_level` (CharField, choices=DIFFICULTY_CHOICES)
- `estimated_minutes` (PositiveIntegerField)
- `order` (PositiveIntegerField)
- `is_published` (BooleanField, default=True)
- `created_at` (DateTimeField, auto_now_add)
- `updated_at` (DateTimeField, auto_now=True)

**Indexes**:
- `idx_topic` on topic
- `idx_difficulty` on difficulty_level
- `idx_published` on is_published
- `idx_order` on order

#### Project
Larger projects for hands-on learning.

**Fields**:
- `id` (PK, AutoField)
- `topic` (ForeignKey to Topic, related_name='projects')
- `title` (CharField, max_length=200)
- `description` (TextField)
- `requirements` (TextField)
- `guidelines` (TextField)
- `starter_template` (TextField, blank=True)
- `sample_solution` (TextField, blank=True)
- `difficulty_level` (CharField, choices=DIFFICULTY_CHOICES)
- `estimated_hours` (PositiveDecimalField, max_digits=3, decimal_places=1)
- `order` (PositiveIntegerField)
- `is_published` (BooleanField, default=True)
- `created_at` (DateTimeField, auto_now_add)
- `updated_at` (DateTimeField, auto_now=True)

**Indexes**:
- `idx_topic` on topic
- `idx_difficulty` on difficulty_level
- `idx_published` on is_published
- `idx_order` on order

### assessments App

#### Quiz
Quiz definitions for assessments.

**Fields**:
- `id` (PK, AutoField)
- `topic` (ForeignKey to Topic, related_name='quizzes')
- `title` (CharField, max_length=200)
- `description` (TextField, blank=True)
- `difficulty_level` (CharField, choices=DIFFICULTY_CHOICES)
- `time_limit_minutes` (PositiveIntegerField, null=True, blank=True)
- `passing_score` (PositiveIntegerField, default=70)
- `is_published` (BooleanField, default=True)
- `created_at` (DateTimeField, auto_now_add)
- `updated_at` (DateTimeField, auto_now=True)

**Indexes**:
- `idx_topic` on topic
- `idx_difficulty` on difficulty_level
- `idx_published` on is_published

#### Question
Quiz questions.

**Fields**:
- `id` (PK, AutoField)
- `quiz` (ForeignKey to Quiz, related_name='questions')
- `question_text` (TextField)
- `question_type` (CharField, choices=QUESTION_TYPE_CHOICES)
- `order` (PositiveIntegerField)
- `points` (PositiveIntegerField, default=1)
- `explanation` (TextField, blank=True)

**Choices**:
- `QUESTION_TYPE_CHOICES`: [('multiple_choice', 'Multiple Choice'), ('true_false', 'True/False'), ('short_answer', 'Short Answer')]

**Indexes**:
- `idx_quiz` on quiz
- `idx_type` on question_type
- `idx_order` on order

#### Answer
Answer options for questions.

**Fields**:
- `id` (PK, AutoField)
- `question` (ForeignKey to Question, related_name='answers')
- `answer_text` (CharField, max_length=500)
- `is_correct` (BooleanField, default=False)
- `order` (PositiveIntegerField)

**Indexes**:
- `idx_question` on question
- `idx_order` on order

#### UserAttempt
User quiz attempts.

**Fields**:
- `id` (PK, AutoField)
- `user` (ForeignKey to User, related_name='quiz_attempts')
- `quiz` (ForeignKey to Quiz, related_name='attempts')
- `score` (PositiveIntegerField)
- `total_points` (PositiveIntegerField)
- `percentage` (PositiveDecimalField, max_digits=5, decimal_places=2)
- `passed` (BooleanField)
- `started_at` (DateTimeField)
- `completed_at` (DateTimeField)
- `time_taken_seconds` (PositiveIntegerField)

**Indexes**:
- `idx_user` on user
- `idx_quiz` on quiz
- `idx_completed` on completed_at

#### UserAnswer
User's answers to quiz questions.

**Fields**:
- `id` (PK, AutoField)
- `attempt` (ForeignKey to UserAttempt, related_name='answers')
- `question` (ForeignKey to Question, related_name='user_answers')
- `selected_answer` (ForeignKey to Answer, related_name='user_selections', null=True, blank=True)
- `text_answer` (TextField, blank=True)
- `is_correct` (BooleanField)
- `points_earned` (PositiveIntegerField, default=0)

**Indexes**:
- `idx_attempt` on attempt
- `idx_question` on question

### progress App

#### ActivityLog
Logs user activities for heatmap and analytics.

**Fields**:
- `id` (PK, AutoField)
- `user` (ForeignKey to User, related_name='activities')
- `activity_type` (CharField, choices=ACTIVITY_TYPE_CHOICES)
- `metadata` (JSONField, blank=True, null=True)
- `timestamp` (DateTimeField, auto_now_add)

**Choices**:
- `ACTIVITY_TYPE_CHOICES`: [('content_viewed', 'Content Viewed'), ('task_completed', 'Task Completed'), ('quiz_taken', 'Quiz Taken'), ('project_started', 'Project Started'), ('project_completed', 'Project Completed'), ('roadmap_created', 'Roadmap Created'), ('day_completed', 'Day Completed')]

**Indexes**:
- `idx_user` on user
- `idx_type` on activity_type
- `idx_timestamp` on timestamp
- `idx_user_timestamp` on (user, timestamp)

#### Progress
Overall progress tracking.

**Fields**:
- `id` (PK, AutoField)
- `user` (ForeignKey to User, related_name='progress')
- `roadmap` (ForeignKey to Roadmap, related_name='progress_records')
- `topic` (ForeignKey to Topic, related_name='progress_records')
- `total_days` (PositiveIntegerField)
- `days_completed` (PositiveIntegerField, default=0)
- `completion_percentage` (PositiveDecimalField, max_digits=5, decimal_places=2)
- `current_day` (PositiveIntegerField, default=1)
- `last_activity_at` (DateTimeField, auto_now=True)
- `started_at` (DateTimeField)
- `completed_at` (DateTimeField, null=True, blank=True)

**Indexes**:
- `idx_user` on user
- `idx_roadmap` on roadmap
- `idx_topic` on topic
- `idx_completion` on completion_percentage

#### Achievement
User achievements and badges.

**Fields**:
- `id` (PK, AutoField)
- `user` (ForeignKey to User, related_name='achievements')
- `achievement_type` (CharField, choices=ACHIEVEMENT_TYPE_CHOICES)
- `title` (CharField, max_length=200)
- `description` (TextField, blank=True)
- `icon` (CharField, max_length=50, blank=True)
- `earned_at` (DateTimeField, auto_now_add)

**Choices**:
- `ACHIEVEMENT_TYPE_CHOICES`: [('first_roadmap', 'First Roadmap'), ['week_streak', '7-Day Streak'), ('month_streak', '30-Day Streak'), ('first_quiz', 'First Quiz'), ('perfect_score', 'Perfect Score'), ('first_project', 'First Project'), ('topic_complete', 'Topic Completed')]

**Indexes**:
- `idx_user` on user
- `idx_type` on achievement_type
- `idx_earned` on earned_at

## Relationships Summary

### User Relationships
- User → UserProfile (1:1)
- User → UserPreferences (1:1)
- User → Roadmap (1:N)
- User → UserAttempt (1:N)
- User → ActivityLog (1:N)
- User → Progress (1:N)
- User → Achievement (1:N)

### Roadmap Relationships
- Roadmap → Day (1:N)
- Roadmap → Progress (1:N)

### Day Relationships
- Day → Module (1:N)

### Topic Relationships
- Topic → TheoryContent (1:N)
- Topic → VisualContent (1:N)
- Topic → PracticeTask (1:N)
- Topic → Project (1:N)
- Topic → Quiz (1:N)
- Topic → Progress (1:N)

### Quiz Relationships
- Quiz → Question (1:N)
- Quiz → Question → Answer (1:N)
- Quiz → UserAttempt (1:N)

### Question Relationships
- Question → Answer (1:N)
- Question → UserAnswer (1:N)

### UserAttempt Relationships
- UserAttempt → UserAnswer (1:N)

## Database Indexes Strategy

### Primary Indexes
- All primary keys are automatically indexed

### Foreign Key Indexes
- All foreign keys have indexes for join optimization

### Composite Indexes
- `ActivityLog`: (user, timestamp) for heatmap queries
- `Roadmap`: (start_date, end_date) for date range queries
- `Day`: (roadmap, day_number) unique constraint

### Selective Indexes
- `is_published`, `is_active`, `is_completed` boolean fields for filtering
- `status` fields for status-based queries
- `difficulty_level` for difficulty-based content retrieval

## Data Integrity

### Constraints
- Unique constraints on usernames, emails, slugs
- Foreign key constraints for referential integrity
- Positive field constraints for numeric fields
- Choice constraints for enum-like fields

### Validation
- Model-level validation in Django
- Database-level constraints where possible
- Custom clean() methods for complex validation

## Migration Strategy

### Initial Migration
- Create all tables with Django migrations
- Seed initial topics and content
- Create admin user

### Future Migrations
- Use Django's migration system for schema changes
- Data migrations for content updates
- Backward-compatible changes when possible

## Performance Considerations

### Query Optimization
- Use select_related() for foreign keys
- Use prefetch_related() for many-to-many (if added)
- Implement pagination for large datasets
- Cache frequently accessed data

### Database Size Management
- Archive old activity logs
- Soft delete instead of hard delete
- Media file storage separate from database

## Security Considerations

### Sensitive Data
- Passwords hashed (Django default)
- No personal identifiable information in logs
- User consent for data collection

### Access Control
- Row-level security via Django permissions
- User-scoped queries in views
- Admin-only access to sensitive data
