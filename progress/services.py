"""
Progress tracking services
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import (
    Badge,
    DailyActivity,
    UserBadge,
    UserLevel,
    UserStreak,
    XPTransaction,
)


class ActivityLogger:
    """Service to log user activities"""
    
    @staticmethod
    def log_day_completion(user, day):
        """Log when a user completes a day"""
        today = timezone.localdate()
        
        # Get or create today's activity
        activity, created = DailyActivity.objects.get_or_create(
            user=user,
            date=today,
            defaults={
                'minutes_studied': int(float(day.estimated_hours) * 60),
                'days_completed': 1,
            }
        )
        
        if not created:
            # Update existing activity
            activity.minutes_studied += int(float(day.estimated_hours) * 60)
            activity.days_completed += 1
            activity.save()
        
        # Update streak
        streak, _ = UserStreak.objects.get_or_create(user=user)
        streak.update_streak()
        
        return activity
    
    @staticmethod
    def get_heatmap_data(user, days=365):
        """Get heatmap data for a positive bounded day window."""
        if (
            isinstance(days, bool)
            or not isinstance(days, int)
            or not 1 <= days <= 3660
        ):
            raise ValueError("days must be an integer between 1 and 3660.")
        today = timezone.localdate()
        start_date = today - timedelta(days=days - 1)
        
        activities = DailyActivity.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=today
        )
        
        # Create dict for quick lookup
        activity_map = {a.date.isoformat(): a.activity_level for a in activities}
        
        # Generate all dates
        heatmap = []
        current = start_date
        while current <= today:
            heatmap.append({
                'date': current.isoformat(),
                'level': activity_map.get(current.isoformat(), 0),
                'day_name': current.strftime('%a'),
            })
            current += timedelta(days=1)
        
        return heatmap
    
    @staticmethod
    def get_user_stats(user):
        """Get comprehensive user statistics"""
        streak, _ = UserStreak.objects.get_or_create(user=user)
        
        total_minutes = (
            DailyActivity.objects.filter(user=user).aggregate(
                total=Sum("minutes_studied")
            )["total"]
            or 0
        )
        
        total_hours = round(total_minutes / 60, 1)
        
        return {
            'current_streak': streak.current_streak,
            'longest_streak': streak.longest_streak,
            'total_days_active': streak.total_days_active,
            'total_hours': total_hours,
            'total_minutes': total_minutes,
        }


class BadgeManager:
    """Service to manage badges and XP rewards."""
    
    @staticmethod
    def get_or_create_user_level(user):
        """Get or create user level."""
        level, created = UserLevel.objects.get_or_create(user=user)
        return level
    
    @staticmethod
    @transaction.atomic
    def add_xp(
        user,
        amount,
        reason,
        *,
        idempotency_key,
        event_type="activity",
        source_object_type="",
        source_object_id="",
        metadata=None,
    ):
        """Atomically award XP once for a deterministic event key."""
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValueError("XP amount must be a positive integer.")
        if not idempotency_key or len(idempotency_key) > 255:
            raise ValueError("A valid XP idempotency key is required.")

        xp_event, created = XPTransaction.objects.get_or_create(
            user=user,
            idempotency_key=idempotency_key,
            defaults={
                "amount": amount,
                "reason": reason[:200],
                "event_type": event_type[:50],
                "source_object_type": source_object_type[:50],
                "source_object_id": str(source_object_id)[:100],
                "metadata": metadata or {},
            },
        )

        level, _ = UserLevel.objects.get_or_create(user=user)
        level = UserLevel.objects.select_for_update().get(pk=level.pk)
        old_level = level.current_level

        if not created:
            return {
                "xp_added": 0,
                "old_level": old_level,
                "new_level": old_level,
                "leveled_up": False,
                "reason": reason,
                "duplicate": True,
                "transaction_id": xp_event.id,
            }

        new_level = level.add_xp(amount)
        return {
            "xp_added": amount,
            "old_level": old_level,
            "new_level": new_level,
            "leveled_up": new_level > old_level,
            "reason": reason,
            "duplicate": False,
            "transaction_id": xp_event.id,
        }

    @staticmethod
    def award_badge(user, badge_name):
        """Manually award a badge to a user."""
        try:
            badge = Badge.objects.get(name=badge_name)
            user_badge, created = UserBadge.objects.get_or_create(
                user=user,
                badge=badge
            )
            
            if created:
                # Award XP for earning badge
                BadgeManager.add_xp(
                    user,
                    badge.xp_reward,
                    f"Earned badge: {badge.name}",
                    idempotency_key=f"badge:{badge.id}",
                    event_type="badge-earned",
                    source_object_type="badge",
                    source_object_id=badge.id,
                )
                return {'success': True, 'badge': badge, 'new': True}
            else:
                return {'success': True, 'badge': badge, 'new': False}
        except Badge.DoesNotExist:
            return {'success': False, 'error': 'Badge not found'}
    
    @staticmethod
    def check_streak_badges(user):
        """Check and award streak-related badges."""
        streak, _ = UserStreak.objects.get_or_create(user=user)
        badges_awarded = []
        
        streak_badges = [
            ('First Steps', 1),
            ('Week Warrior', 7),
            ('Fortnight Fighter', 14),
            ('Monthly Master', 30),
            ('Century Champion', 100),
        ]
        
        for badge_name, required_streak in streak_badges:
            if streak.current_streak >= required_streak:
                result = BadgeManager.award_badge(user, badge_name)
                if result.get('success') and result.get('new'):
                    badges_awarded.append(result['badge'])
        
        return badges_awarded
    
    @staticmethod
    def check_learning_badges(user):
        """Check and award learning-related badges."""
        from learning.models import Roadmap, Day
        badges_awarded = []
        
        # First Roadmap
        if Roadmap.objects.filter(user=user).exists():
            result = BadgeManager.award_badge(user, 'First Roadmap')
            if result.get('success') and result.get('new'):
                badges_awarded.append(result['badge'])
        
        # Completed roadmaps
        completed_roadmaps = Roadmap.objects.filter(user=user, status='completed').count()
        if completed_roadmaps >= 1:
            result = BadgeManager.award_badge(user, 'Roadmap Master')
            if result.get('success') and result.get('new'):
                badges_awarded.append(result['badge'])
        
        # Topics completed (days completed)
        total_days = Day.objects.filter(
            roadmap__user=user,
            is_completed=True
        ).count()
        
        learning_badges = [
            ('Bookworm', 10),
            ('Scholar', 50),
            ('Genius', 100),
        ]
        
        for badge_name, required_days in learning_badges:
            if total_days >= required_days:
                result = BadgeManager.award_badge(user, badge_name)
                if result.get('success') and result.get('new'):
                    badges_awarded.append(result['badge'])
        
        return badges_awarded
    
    @staticmethod
    def check_practice_badges(user):
        """Check and award practice-related badges."""
        from practice.models import CodeReview
        badges_awarded = []
        
        # Code reviews count
        review_count = CodeReview.objects.filter(user=user).count()
        
        practice_badges = [
            ('Code Newbie', 1),
            ('Code Enthusiast', 10),
            ('Code Wizard', 50),
            ('Code Master', 100),
        ]
        
        for badge_name, required_reviews in practice_badges:
            if review_count >= required_reviews:
                result = BadgeManager.award_badge(user, badge_name)
                if result.get('success') and result.get('new'):
                    badges_awarded.append(result['badge'])
        
        return badges_awarded
    
    @staticmethod
    def check_test_badges(user):
        """Check and award test-related badges."""
        from assessments.models import TestAttempt
        badges_awarded = []
        
        # First test
        if TestAttempt.objects.filter(user=user).exists():
            result = BadgeManager.award_badge(user, 'Test Taker')
            if result.get('success') and result.get('new'):
                badges_awarded.append(result['badge'])
        
        # Tests completed
        test_count = TestAttempt.objects.filter(user=user, completed_at__isnull=False).count()
        if test_count >= 10:
            result = BadgeManager.award_badge(user, 'Test Champion')
            if result.get('success') and result.get('new'):
                badges_awarded.append(result['badge'])
        
        # Score-based badges
        for attempt in TestAttempt.objects.filter(user=user, completed_at__isnull=False):
            percentage = attempt.percentage
            
            if percentage >= 60:
                result = BadgeManager.award_badge(user, 'Passing Grade')
                if result.get('success') and result.get('new'):
                    badges_awarded.append(result['badge'])
            
            if percentage >= 80:
                result = BadgeManager.award_badge(user, 'Excellence')
                if result.get('success') and result.get('new'):
                    badges_awarded.append(result['badge'])
            
            if percentage >= 100:
                result = BadgeManager.award_badge(user, 'Perfect Score')
                if result.get('success') and result.get('new'):
                    badges_awarded.append(result['badge'])
        
        return badges_awarded
    
    @staticmethod
    def check_special_badges(user):
        """Check and award special badges."""
        from learning.models import Day
        badges_awarded = []
        
        # Early Bird - study before 7 AM
        early_morning_completions = Day.objects.filter(
            roadmap__user=user,
            is_completed=True,
            completed_at__hour__lt=7
        ).count()
        
        if early_morning_completions >= 1:
            result = BadgeManager.award_badge(user, 'Early Bird')
            if result.get('success') and result.get('new'):
                badges_awarded.append(result['badge'])
        
        # Night Owl - study after 11 PM
        late_night_completions = Day.objects.filter(
            roadmap__user=user,
            is_completed=True,
            completed_at__hour__gte=23
        ).count()
        
        if late_night_completions >= 1:
            result = BadgeManager.award_badge(user, 'Night Owl')
            if result.get('success') and result.get('new'):
                badges_awarded.append(result['badge'])
        
        # Anniversary - 1 year on platform
        account_age = timezone.now() - user.date_joined
        if account_age.days >= 365:
            result = BadgeManager.award_badge(user, 'Anniversary')
            if result.get('success') and result.get('new'):
                badges_awarded.append(result['badge'])
        
        # Beta Tester - early user (first 100 users)
        if user.id <= 100:
            result = BadgeManager.award_badge(user, 'Beta Tester')
            if result.get('success') and result.get('new'):
                badges_awarded.append(result['badge'])
        
        return badges_awarded
    
    @staticmethod
    def check_and_award_badges(user):
        """Check all badges and award new ones."""
        all_badges = []
        
        all_badges.extend(BadgeManager.check_streak_badges(user))
        all_badges.extend(BadgeManager.check_learning_badges(user))
        all_badges.extend(BadgeManager.check_practice_badges(user))
        all_badges.extend(BadgeManager.check_test_badges(user))
        all_badges.extend(BadgeManager.check_special_badges(user))
        
        return all_badges
    
    @staticmethod
    def get_badge_progress(user, badge):
        """Calculate progress percentage for a locked badge."""
        from learning.models import Roadmap, Day
        from assessments.models import TestAttempt
        
        requirement_type = badge.requirement_type
        requirement_value = badge.requirement_value
        current_value = 0
        
        if requirement_type == 'streak_days':
            streak, _ = UserStreak.objects.get_or_create(user=user)
            current_value = streak.current_streak
        elif requirement_type == 'topics_completed':
            current_value = Day.objects.filter(
                roadmap__user=user,
                is_completed=True
            ).count()
        elif requirement_type == 'roadmaps_created':
            current_value = Roadmap.objects.filter(user=user).count()
        elif requirement_type == 'roadmaps_completed':
            current_value = Roadmap.objects.filter(user=user, status='completed').count()
        elif requirement_type == 'code_reviews':
            # CodeReview is introduced with the trusted
            # activity ledger in Phase 3. Until then,
            # safely report zero instead of crashing.
            try:
                from practice.models import CodeReview
            except ImportError:
                current_value = 0
            else:
                current_value = CodeReview.objects.filter(
                    user=user
                ).count()
        elif requirement_type == 'tests_taken':
            current_value = TestAttempt.objects.filter(user=user).count()
        elif requirement_type == 'tests_completed':
            current_value = TestAttempt.objects.filter(user=user, completed_at__isnull=False).count()
        elif requirement_type == 'test_score':
            # Get best score
            best_score = 0
            for attempt in TestAttempt.objects.filter(user=user, completed_at__isnull=False):
                if attempt.percentage > best_score:
                    best_score = attempt.percentage
            current_value = best_score
        elif requirement_type == 'early_study':
            current_value = Day.objects.filter(
                roadmap__user=user,
                is_completed=True,
                completed_at__hour__lt=7
            ).count()
        elif requirement_type == 'late_study':
            current_value = Day.objects.filter(
                roadmap__user=user,
                is_completed=True,
                completed_at__hour__gte=23
            ).count()
        elif requirement_type == 'account_age':
            from django.utils import timezone
            account_age = (timezone.now() - user.date_joined).days
            current_value = account_age
        elif requirement_type == 'early_user':
            current_value = user.id
        
        # Calculate percentage
        if requirement_value == 0:
            return 0
        
        progress = min(100, round((current_value / requirement_value) * 100, 1))
        return {
            'current': current_value,
            'required': requirement_value,
            'percentage': progress
        }

class AnalyticsService:
    """Service to generate analytics data"""
    
    @staticmethod
    def get_weekly_activity(user, weeks=4):
        """Get activity data for last N weeks"""
        from datetime import timedelta
        from django.utils import timezone
        
        today = timezone.localdate()
        start_date = today - timedelta(days=(weeks * 7) - 1)
        
        activities = DailyActivity.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=today
        ).order_by('date')
        
        # Create dict for quick lookup
        activity_map = {a.date.isoformat(): a.minutes_studied for a in activities}
        
        # Generate all dates
        labels = []
        data = []
        current = start_date
        while current <= today:
            labels.append(current.strftime('%b %d'))
            data.append(activity_map.get(current.isoformat(), 0))
            current += timedelta(days=1)
        
        return {
            'labels': labels,
            'data': data
        }
    
    @staticmethod
    def get_topic_distribution(user):
        """Get time spent per topic"""
        from learning.models import Roadmap
        
        roadmaps = Roadmap.objects.filter(user=user).annotate(
            completed_days_count=Count(
                "days",
                filter=Q(days__is_completed=True),
            )
        )

        topic_data = {}
        for roadmap in roadmaps:
            topic_name = roadmap.get_topic_display()
            hours = float(roadmap.completed_days) * float(roadmap.daily_hours)
            
            if topic_name in topic_data:
                topic_data[topic_name] += hours
            else:
                topic_data[topic_name] = hours
        
        return {
            'labels': list(topic_data.keys()),
            'data': list(topic_data.values())
        }
    
    @staticmethod
    def get_test_performance(user):
        """Return the latest twenty completed, scoreable tests in time order."""
        from assessments.models import Test

        tests = list(
            Test.objects.filter(
                user=user,
                status="completed",
                completed_at__isnull=False,
                score__isnull=False,
            ).order_by("-completed_at")[:20]
        )
        tests.reverse()
        return {
            "labels": [test.completed_at.strftime("%b %d") for test in tests],
            "data": [test.percentage for test in tests],
        }
    
    @staticmethod
    def get_learning_stats(user):
        """Get comprehensive learning statistics"""
        from assessments.models import Test
        from learning.models import Day, Roadmap

        # Roadmaps
        total_roadmaps = Roadmap.objects.filter(user=user).count()
        active_roadmaps = Roadmap.objects.filter(user=user, status='active').count()
        completed_roadmaps = Roadmap.objects.filter(user=user, status='completed').count()
        
        # Days
        total_days = Day.objects.filter(roadmap__user=user).count()
        completed_days = Day.objects.filter(roadmap__user=user, is_completed=True).count()
        
        # Activity
        total_activity_days = DailyActivity.objects.filter(user=user).count()
        total_minutes = DailyActivity.objects.filter(user=user).aggregate(
            total=Sum('minutes_studied')
        )['total'] or 0
        
        # Streak
        streak, _ = UserStreak.objects.get_or_create(user=user)
        
        completed_tests = list(
            Test.objects.filter(
                user=user,
                status="completed",
                completed_at__isnull=False,
                score__isnull=False,
            )
        )
        percentages = [test.percentage for test in completed_tests]
        total_tests = len(completed_tests)
        avg_score = (
            sum(percentages) / len(percentages)
            if percentages
            else 0
        )

        avg_daily_minutes = total_minutes / max(total_activity_days, 1)
        
        return {
            'total_roadmaps': total_roadmaps,
            'active_roadmaps': active_roadmaps,
            'completed_roadmaps': completed_roadmaps,
            'total_days': total_days,
            'completed_days': completed_days,
            'completion_rate': round((completed_days / max(total_days, 1)) * 100, 1),
            'total_activity_days': total_activity_days,
            'total_minutes': total_minutes,
            'total_hours': round(total_minutes / 60, 1),
            'avg_daily_minutes': round(avg_daily_minutes, 1),
            'current_streak': streak.current_streak,
            'longest_streak': streak.longest_streak,
            'total_tests': total_tests,
            'avg_test_score': round(avg_score, 1),
        }
    
    @staticmethod
    def get_study_consistency(user, days=30):
        """Calculate bounded study consistency for a positive day window."""
        if (
            isinstance(days, bool)
            or not isinstance(days, int)
            or not 1 <= days <= 3660
        ):
            raise ValueError("days must be an integer between 1 and 3660.")

        today = timezone.localdate()
        start_date = today - timedelta(days=days - 1)
        
        active_days = DailyActivity.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=today,
            minutes_studied__gt=0
        ).count()
        
        consistency = (active_days / days) * 100
        return round(consistency, 1)