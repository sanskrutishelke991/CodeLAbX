from django.core.management.base import BaseCommand
from progress.models import Badge


class Command(BaseCommand):
    help = 'Seed badges for the achievements system'

    def handle(self, *args, **options):
        badges_data = [
            # STREAK BADGES
            {
                'name': 'First Steps',
                'description': 'Complete your first day of learning',
                'icon': '🌱',
                'category': 'streak',
                'rarity': 'common',
                'xp_reward': 10,
                'requirement_type': 'streak_days',
                'requirement_value': 1,
                'color': '#a0a0a0'
            },
            {
                'name': 'Week Warrior',
                'description': 'Maintain a 7-day learning streak',
                'icon': '🔥',
                'category': 'streak',
                'rarity': 'common',
                'xp_reward': 50,
                'requirement_type': 'streak_days',
                'requirement_value': 7,
                'color': '#a0a0a0'
            },
            {
                'name': 'Fortnight Fighter',
                'description': 'Maintain a 14-day learning streak',
                'icon': '⚡',
                'category': 'streak',
                'rarity': 'rare',
                'xp_reward': 100,
                'requirement_type': 'streak_days',
                'requirement_value': 14,
                'color': '#4a90e2'
            },
            {
                'name': 'Monthly Master',
                'description': 'Maintain a 30-day learning streak',
                'icon': '💎',
                'category': 'streak',
                'rarity': 'epic',
                'xp_reward': 250,
                'requirement_type': 'streak_days',
                'requirement_value': 30,
                'color': '#a855f7'
            },
            {
                'name': 'Century Champion',
                'description': 'Maintain a 100-day learning streak',
                'icon': '👑',
                'category': 'streak',
                'rarity': 'legendary',
                'xp_reward': 1000,
                'requirement_type': 'streak_days',
                'requirement_value': 100,
                'color': '#f59e0b'
            },
            
            # LEARNING BADGES
            {
                'name': 'Bookworm',
                'description': 'Complete 10 learning topics',
                'icon': '📚',
                'category': 'learning',
                'rarity': 'common',
                'xp_reward': 50,
                'requirement_type': 'topics_completed',
                'requirement_value': 10,
                'color': '#a0a0a0'
            },
            {
                'name': 'Scholar',
                'description': 'Complete 50 learning topics',
                'icon': '🎓',
                'category': 'learning',
                'rarity': 'rare',
                'xp_reward': 200,
                'requirement_type': 'topics_completed',
                'requirement_value': 50,
                'color': '#4a90e2'
            },
            {
                'name': 'Genius',
                'description': 'Complete 100 learning topics',
                'icon': '🧠',
                'category': 'learning',
                'rarity': 'epic',
                'xp_reward': 500,
                'requirement_type': 'topics_completed',
                'requirement_value': 100,
                'color': '#a855f7'
            },
            {
                'name': 'First Roadmap',
                'description': 'Create your first learning roadmap',
                'icon': '🚀',
                'category': 'learning',
                'rarity': 'common',
                'xp_reward': 25,
                'requirement_type': 'roadmaps_created',
                'requirement_value': 1,
                'color': '#a0a0a0'
            },
            {
                'name': 'Roadmap Master',
                'description': 'Complete a full learning roadmap',
                'icon': '🎯',
                'category': 'learning',
                'rarity': 'rare',
                'xp_reward': 300,
                'requirement_type': 'roadmaps_completed',
                'requirement_value': 1,
                'color': '#4a90e2'
            },
            
            # PRACTICE BADGES
            {
                'name': 'Code Newbie',
                'description': 'Use Code Examiner for the first time',
                'icon': '💻',
                'category': 'practice',
                'rarity': 'common',
                'xp_reward': 25,
                'requirement_type': 'code_reviews',
                'requirement_value': 1,
                'color': '#a0a0a0'
            },
            {
                'name': 'Code Enthusiast',
                'description': 'Review 10 pieces of code',
                'icon': '⚙️',
                'category': 'practice',
                'rarity': 'common',
                'xp_reward': 75,
                'requirement_type': 'code_reviews',
                'requirement_value': 10,
                'color': '#a0a0a0'
            },
            {
                'name': 'Code Wizard',
                'description': 'Review 50 pieces of code',
                'icon': '🔧',
                'category': 'practice',
                'rarity': 'rare',
                'xp_reward': 250,
                'requirement_type': 'code_reviews',
                'requirement_value': 50,
                'color': '#4a90e2'
            },
            {
                'name': 'Code Master',
                'description': 'Review 100 pieces of code',
                'icon': '🏆',
                'category': 'practice',
                'rarity': 'epic',
                'xp_reward': 500,
                'requirement_type': 'code_reviews',
                'requirement_value': 100,
                'color': '#a855f7'
            },
            
            # TEST BADGES
            {
                'name': 'Test Taker',
                'description': 'Take your first test',
                'icon': '📝',
                'category': 'test',
                'rarity': 'common',
                'xp_reward': 20,
                'requirement_type': 'tests_taken',
                'requirement_value': 1,
                'color': '#a0a0a0'
            },
            {
                'name': 'Passing Grade',
                'description': 'Score 60% or higher on a test',
                'icon': '✅',
                'category': 'test',
                'rarity': 'common',
                'xp_reward': 30,
                'requirement_type': 'test_score',
                'requirement_value': 60,
                'color': '#a0a0a0'
            },
            {
                'name': 'Excellence',
                'description': 'Score 80% or higher on a test',
                'icon': '🌟',
                'category': 'test',
                'rarity': 'rare',
                'xp_reward': 75,
                'requirement_type': 'test_score',
                'requirement_value': 80,
                'color': '#4a90e2'
            },
            {
                'name': 'Perfect Score',
                'description': 'Score 100% on a test',
                'icon': '💯',
                'category': 'test',
                'rarity': 'epic',
                'xp_reward': 200,
                'requirement_type': 'test_score',
                'requirement_value': 100,
                'color': '#a855f7'
            },
            {
                'name': 'Test Champion',
                'description': 'Complete 10 tests',
                'icon': '🎪',
                'category': 'test',
                'rarity': 'rare',
                'xp_reward': 150,
                'requirement_type': 'tests_completed',
                'requirement_value': 10,
                'color': '#4a90e2'
            },
            
            # SPECIAL BADGES
            {
                'name': 'Early Bird',
                'description': 'Study before 7 AM',
                'icon': '🌅',
                'category': 'special',
                'rarity': 'rare',
                'xp_reward': 100,
                'requirement_type': 'early_study',
                'requirement_value': 1,
                'color': '#4a90e2'
            },
            {
                'name': 'Night Owl',
                'description': 'Study after 11 PM',
                'icon': '🦉',
                'category': 'special',
                'rarity': 'rare',
                'xp_reward': 100,
                'requirement_type': 'late_study',
                'requirement_value': 1,
                'color': '#4a90e2'
            },
            {
                'name': 'Anniversary',
                'description': '1 year on CodeLabX',
                'icon': '🎂',
                'category': 'special',
                'rarity': 'legendary',
                'xp_reward': 500,
                'requirement_type': 'account_age',
                'requirement_value': 365,
                'color': '#f59e0b'
            },
            {
                'name': 'Beta Tester',
                'description': 'Early CodeLabX user',
                'icon': '⭐',
                'category': 'special',
                'rarity': 'legendary',
                'xp_reward': 250,
                'requirement_type': 'early_user',
                'requirement_value': 100,
                'color': '#f59e0b'
            },
        ]
        
        created_count = 0
        updated_count = 0
        
        for badge_data in badges_data:
            badge, created = Badge.objects.update_or_create(
                name=badge_data['name'],
                defaults=badge_data,
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created badge: {badge.icon} {badge.name}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Badge already exists: {badge.icon} {badge.name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary: {created_count} badges created, {updated_count} already exist. Total: {Badge.objects.count()}'
            )
        )
