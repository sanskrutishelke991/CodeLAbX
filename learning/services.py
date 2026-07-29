"""
Roadmap Generation Service

This service handles the generation of learning roadmaps based on user preferences.
For MVP, it uses rule-based generation with curated topic templates.
"""

from datetime import datetime, timedelta
from django.utils import timezone
from .models import Roadmap, Day


class RoadmapGenerator:
    """Service class for generating learning roadmaps."""
    
    # Curated topic templates for MVP
    TOPIC_TEMPLATES = {
        'ML': {
            'name': 'Machine Learning',
            'modules': [
                'Introduction to ML',
                'Python for ML',
                'Linear Algebra Basics',
                'Statistics & Probability',
                'Data Preprocessing',
                'Supervised Learning',
                'Unsupervised Learning',
                'Neural Networks',
                'Deep Learning',
                'Model Evaluation',
                'Feature Engineering',
                'Ensemble Methods',
                'Model Deployment',
                'ML Projects',
                'Advanced Topics'
            ]
        },
        'DSA': {
            'name': 'Data Structures & Algorithms',
            'modules': [
                'Introduction to DSA',
                'Time & Space Complexity',
                'Arrays & Strings',
                'Linked Lists',
                'Stacks & Queues',
                'Trees & Binary Trees',
                'Heaps & Priority Queues',
                'Hash Tables',
                'Recursion',
                'Sorting Algorithms',
                'Searching Algorithms',
                'Graphs Basics',
                'Graph Traversal',
                'Dynamic Programming',
                'Greedy Algorithms',
                'Advanced Data Structures',
                'Algorithm Design',
                'DSA Projects'
            ]
        }
    }
    
    @classmethod
    def generate_roadmap(cls, user, topic, duration_months, daily_hours, level='beginner', start_date=None):
        """
        Generate a complete roadmap with day-by-day structure.
        
        Args:
            user: User object
            topic: Topic code (ML or DSA)
            duration_months: Duration in months
            daily_hours: Daily study hours
            level: Difficulty level (beginner, intermediate, advanced)
            start_date: Optional start date
            
        Returns:
            Roadmap object with associated Day objects
        """
        # Calculate total days
        total_days = duration_months * 30
        
        # Create roadmap
        roadmap = Roadmap.objects.create(
            user=user,
            topic=topic,
            title=f"{cls.TOPIC_TEMPLATES[topic]['name']} Roadmap",
            description=f"A {duration_months}-month learning path for {cls.TOPIC_TEMPLATES[topic]['name']} at {level} level.",
            total_days=total_days,
            daily_hours=daily_hours,
            level=level,
            start_date=start_date
        )
        
        # Calculate end date if start date provided
        if start_date:
            roadmap.end_date = start_date + timedelta(days=total_days)
            roadmap.save()
        
        # Generate days using rule-based distribution
        cls._generate_days(roadmap, topic, total_days, daily_hours, level)
        
        return roadmap
    
    @classmethod
    def _generate_days(cls, roadmap, topic, total_days, daily_hours, level):
        """
        Generate day-by-day structure for the roadmap.
        
        Uses rule-based distribution to spread modules across the duration.
        """
        modules = cls.TOPIC_TEMPLATES[topic]['modules']
        num_modules = len(modules)
        
        # Calculate days per module (with remainder distribution)
        days_per_module = total_days // num_modules
        remainder = total_days % num_modules
        
        # Adjust for difficulty level
        if level == 'beginner':
            days_per_module = max(days_per_module, 3)  # Minimum 3 days per module
        elif level == 'intermediate':
            days_per_module = max(days_per_module, 2)  # Minimum 2 days per module
        elif level == 'advanced':
            days_per_module = max(days_per_module, 1)  # Minimum 1 day per module
        
        current_day = 1
        
        for module_idx, module_name in enumerate(modules):
            # Distribute remainder across first few modules
            module_days = days_per_module + (1 if module_idx < remainder else 0)
            
            # Generate days for this module
            for day_in_module in range(1, module_days + 1):
                if current_day > total_days:
                    break
                
                day_title = cls._generate_day_title(module_name, day_in_module, module_days)
                day_description = cls._generate_day_description(module_name, day_in_module, module_days, level)
                estimated_hours = daily_hours
                
                Day.objects.create(
                    roadmap=roadmap,
                    day_number=current_day,
                    title=day_title,
                    description=day_description,
                    estimated_hours=estimated_hours,
                    order=current_day
                )
                
                current_day += 1
    
    @classmethod
    def _generate_day_title(cls, module_name, day_in_module, total_module_days):
        """Generate a descriptive title for a specific day."""
        if total_module_days == 1:
            return f"{module_name}"
        elif day_in_module == 1:
            return f"{module_name}: Introduction"
        elif day_in_module == total_module_days:
            return f"{module_name}: Practice & Review"
        else:
            return f"{module_name}: Part {day_in_module}"
    
    @classmethod
    def _generate_day_description(cls, module_name, day_in_module, total_module_days, level):
        """Generate a description for a specific day."""
        descriptions = {
            'beginner': {
                'intro': 'Learn the fundamentals with examples and basic exercises.',
                'middle': 'Continue learning with hands-on practice and problem-solving.',
                'end': 'Review concepts and complete practice exercises to reinforce learning.'
            },
            'intermediate': {
                'intro': 'Deep dive into concepts with advanced examples.',
                'middle': 'Work on complex problems and real-world applications.',
                'end': 'Solve challenging problems and review key concepts.'
            },
            'advanced': {
                'intro': 'Master advanced concepts and optimization techniques.',
                'middle': 'Work on expert-level problems and edge cases.',
                'end': 'Complete comprehensive review and advanced problem-solving.'
            }
        }
        
        if total_module_days == 1:
            return descriptions[level]['middle']
        elif day_in_module == 1:
            return descriptions[level]['intro']
        elif day_in_module == total_module_days:
            return descriptions[level]['end']
        else:
            return descriptions[level]['middle']
    
    @classmethod
    def get_available_topics(cls):
        """Return list of available topics for roadmap creation."""
        return [
            {'code': code, 'name': data['name']}
            for code, data in cls.TOPIC_TEMPLATES.items()
        ]
    
    @classmethod
    def estimate_completion_date(cls, start_date, duration_months):
        """Calculate estimated completion date based on start date and duration."""
        if not start_date:
            return None
        return start_date + timedelta(days=duration_months * 30)
