from django.core.management.base import BaseCommand
from content.models import VideoCategory, Video


class Command(BaseCommand):
    help = 'Seed video categories and sample videos'
    
    def handle(self, *args, **kwargs):
        # Create categories
        categories_data = [
            {'name': 'Python', 'slug': 'python', 'icon': '🐍', 'color': '#4B8BBE', 'order': 1},
            {'name': 'Machine Learning', 'slug': 'ml', 'icon': '🤖', 'color': '#FF6B6B', 'order': 2},
            {'name': 'Data Structures', 'slug': 'dsa', 'icon': '🗂️', 'color': '#6C63FF', 'order': 3},
            {'name': 'Web Development', 'slug': 'web', 'icon': '🌐', 'color': '#00D4AA', 'order': 4},
            {'name': 'AI & Deep Learning', 'slug': 'ai', 'icon': '🧠', 'color': '#a855f7', 'order': 5},
            {'name': 'Databases', 'slug': 'db', 'icon': '💾', 'color': '#f59e0b', 'order': 6},
        ]
        
        categories = {}
        for cat_data in categories_data:
            cat, created = VideoCategory.objects.update_or_create(
                slug=cat_data['slug'],
                defaults=cat_data,
            )
            categories[cat_data['slug']] = cat
            status = 'Created' if created else 'Updated'
            self.stdout.write(f"{status}: {cat.name}")
        
        # Sample videos (Popular ones on YouTube)
        videos_data = [
            # Python
            {
                'title': 'Python Full Course for Beginners',
                'description': 'Complete Python tutorial covering all fundamentals',
                'youtube_id': 'rfscVS0vtbw',
                'category': 'python',
                'difficulty': 'beginner',
                'channel_name': 'freeCodeCamp',
                'duration': '4:26:52',
                'tags': ['python', 'basics', 'tutorial'],
                'is_featured': True,
            },
            {
                'title': 'Python Object Oriented Programming',
                'description': 'Learn OOP concepts in Python with examples',
                'youtube_id': 'JeznW_7DlB0',
                'category': 'python',
                'difficulty': 'intermediate',
                'channel_name': 'Tech With Tim',
                'duration': '1:00:00',
                'tags': ['python', 'oop', 'classes'],
            },
            
            # Machine Learning
            {
                'title': 'Machine Learning Full Course',
                'description': 'Complete Machine Learning course from scratch',
                'youtube_id': 'GwIo3gDZCVQ',
                'category': 'ml',
                'difficulty': 'beginner',
                'channel_name': 'Great Learning',
                'duration': '10:00:00',
                'tags': ['ml', 'ai', 'tutorial'],
                'is_featured': True,
            },
            {
                'title': 'Linear Regression - Machine Learning',
                'description': 'Understanding Linear Regression algorithm',
                'youtube_id': 'nk2CQITm_eo',
                'category': 'ml',
                'difficulty': 'intermediate',
                'channel_name': 'StatQuest',
                'duration': '27:26',
                'tags': ['ml', 'regression', 'statistics'],
            },
            
            # DSA
            {
                'title': 'Data Structures and Algorithms Course',
                'description': 'Complete DSA course with implementations',
                'youtube_id': '8hly31xKli0',
                'category': 'dsa',
                'difficulty': 'beginner',
                'channel_name': 'freeCodeCamp',
                'duration': '10:00:00',
                'tags': ['dsa', 'algorithms', 'coding'],
                'is_featured': True,
            },
            {
                'title': 'Big O Notation Explained',
                'description': 'Understanding time complexity and Big O',
                'youtube_id': 'Mo4vesaut8g',
                'category': 'dsa',
                'difficulty': 'intermediate',
                'channel_name': 'Web Dev Simplified',
                'duration': '17:20',
                'tags': ['dsa', 'complexity', 'algorithms'],
            },
            
            # Web Dev
            {
                'title': 'Django For Beginners',
                'description': 'Complete Django framework tutorial',
                'youtube_id': 'rHux0gMZ3Eg',
                'category': 'web',
                'difficulty': 'beginner',
                'channel_name': 'Traversy Media',
                'duration': '1:20:00',
                'tags': ['django', 'web', 'python'],
                'is_featured': True,
            },
            {
                'title': 'HTML CSS JavaScript Full Course',
                'description': 'Frontend web development basics',
                'youtube_id': 'G3e-cpL7ofc',
                'category': 'web',
                'difficulty': 'beginner',
                'channel_name': 'SuperSimpleDev',
                'duration': '3:00:00',
                'tags': ['html', 'css', 'javascript'],
            },
            
            # AI
            {
                'title': 'Neural Networks Explained',
                'description': 'Understanding how neural networks work',
                'youtube_id': 'aircAruvnKk',
                'category': 'ai',
                'difficulty': 'intermediate',
                'channel_name': '3Blue1Brown',
                'duration': '19:13',
                'tags': ['ai', 'neural-networks', 'deep-learning'],
                'is_featured': True,
            },
            {
                'title': 'Deep Learning Crash Course',
                'description': 'Introduction to Deep Learning',
                'youtube_id': 'VyWAvY2CF9c',
                'category': 'ai',
                'difficulty': 'intermediate',
                'channel_name': 'freeCodeCamp',
                'duration': '1:25:00',
                'tags': ['ai', 'deep-learning', 'tensorflow'],
            },
            
            # Databases
            {
                'title': 'SQL Full Course for Beginners',
                'description': 'Learn SQL from scratch',
                'youtube_id': 'HXV3zeQKqGY',
                'category': 'db',
                'difficulty': 'beginner',
                'channel_name': 'freeCodeCamp',
                'duration': '4:20:00',
                'tags': ['sql', 'database'],
                'is_featured': True,
            },
        ]
        
        created_count = 0
        updated_count = 0
        for video_data in videos_data:
            category_slug = video_data.pop('category')
            video_data['category'] = categories[category_slug]
            
            video, created = Video.objects.update_or_create(
                youtube_id=video_data['youtube_id'],
                defaults=video_data,
            )
            
            if created:
                created_count += 1
                self.stdout.write(f"Created: {video.title}")
            else:
                updated_count += 1
                self.stdout.write(f"Updated: {video.title}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSeeded {len(categories)} categories; "
                f"{created_count} videos created and {updated_count} updated."
            )
        )