from __future__ import annotations

import json
from pathlib import Path

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from learning.models import Day, Roadmap

from .models import (
    LearnerIntelligenceProfile,
    PublicShare,
    Skill,
    SkillPack,
)
from .services.evidence import record_learning_event
from .services.public_sharing import (
    create_or_refresh_public_share,
    refresh_public_share,
    revoke_public_share,
)
from .services.skill_packs import seed_skill_packs


class PublicSharingTests(TestCase):
    def setUp(self):
        seed_skill_packs()
        self.user = User.objects.create_user(
            username="share-private-owner",
            email="owner-private@example.com",
            password="StrongPass123!",
        )
        self.other = User.objects.create_user(
            username="share-other-user",
            email="other-private@example.com",
            password="StrongPass123!",
        )
        self.pack = SkillPack.objects.get(code="programming_dsa", version=1)
        now = timezone.now()
        self.profile = LearnerIntelligenceProfile.objects.create(
            user=self.user,
            primary_goal="placement",
            selected_pack=self.pack,
            routing_diagnostic_completed_at=now,
            goal_diagnostic_completed_at=now,
        )
        self.other_profile = LearnerIntelligenceProfile.objects.create(
            user=self.other,
            primary_goal="placement",
            selected_pack=self.pack,
            routing_diagnostic_completed_at=now,
            goal_diagnostic_completed_at=now,
        )
        self.skill = Skill.objects.get(code="programming.debugging")
        record_learning_event(
            user=self.user,
            skill_code=self.skill.code,
            event_type="assessment_answer",
            source_type="PRIVATE_ASSESSMENT_SOURCE",
            source_id="PRIVATE_SOURCE_ID",
            idempotency_key="public-sharing-evidence-1",
            outcome=1,
        )
        self.roadmap = Roadmap.objects.create(
            user=self.user,
            topic="DSA",
            title="Public-safe roadmap title",
            description="PRIVATE_ROADMAP_DESCRIPTION",
            total_days=2,
            daily_hours=1,
        )
        Day.objects.create(
            roadmap=self.roadmap,
            day_number=1,
            title="Arrays practice",
            description="PRIVATE_DAY_DESCRIPTION",
            estimated_hours=1,
            order=1,
            is_completed=True,
            completed_at=now,
            ai_content="PRIVATE_GENERATED_LESSON_CONTENT",
        )
        Day.objects.create(
            roadmap=self.roadmap,
            day_number=2,
            title="Hash maps practice",
            description="PRIVATE_DAY_TWO_DESCRIPTION",
            estimated_hours=1,
            order=2,
        )

    def create_passport_share(self, **kwargs):
        values = {
            "share_type": "passport",
            "display_name": "CodeLabX learner",
            "include_evidence_counts": True,
        }
        values.update(kwargs)
        return create_or_refresh_public_share(self.user, **values).share

    def create_roadmap_share(self, **kwargs):
        values = {
            "share_type": "roadmap",
            "roadmap": self.roadmap,
            "display_name": "CodeLabX learner",
            "include_completed_items": True,
        }
        values.update(kwargs)
        return create_or_refresh_public_share(self.user, **values).share

    def test_passport_snapshot_is_minimized_and_not_verification(self):
        share = self.create_passport_share()
        snapshot = share.snapshot
        serialized = json.dumps(snapshot)
        self.assertEqual(snapshot["kind"], "passport")
        self.assertEqual(snapshot["observed_skill_count"], 1)
        self.assertEqual(snapshot["skills"][0]["name"], self.skill.name)
        self.assertIn("not independently verified", snapshot["trust_label"])
        self.assertNotIn(self.user.username, serialized)
        self.assertNotIn(self.user.email, serialized)
        self.assertNotIn("PRIVATE_ASSESSMENT_SOURCE", serialized)
        self.assertNotIn("PRIVATE_SOURCE_ID", serialized)
        self.assertNotIn("idempotency", serialized)
        self.assertEqual(len(share.snapshot_hash), 64)

    def test_evidence_counts_are_explicitly_optional(self):
        share = self.create_passport_share(include_evidence_counts=False)
        self.assertNotIn("evidence", share.snapshot["skills"][0])
        self.assertFalse(share.include_evidence_counts)

    def test_roadmap_snapshot_excludes_descriptions_content_and_identity(self):
        share = self.create_roadmap_share()
        serialized = json.dumps(share.snapshot)
        self.assertEqual(share.snapshot["roadmap"]["completed_days"], 1)
        self.assertEqual(len(share.snapshot["days"]), 2)
        self.assertIn("Arrays practice", serialized)
        for private_value in (
            "PRIVATE_ROADMAP_DESCRIPTION",
            "PRIVATE_DAY_DESCRIPTION",
            "PRIVATE_GENERATED_LESSON_CONTENT",
            self.user.username,
            self.user.email,
        ):
            self.assertNotIn(private_value, serialized)
        self.assertIn("not a certificate", share.snapshot["trust_label"])

    def test_snapshot_is_frozen_until_explicit_refresh(self):
        share = self.create_passport_share()
        original_hash = share.snapshot_hash
        original_count = share.snapshot["observed_skill_count"]
        another = Skill.objects.get(code="python.syntax_types")
        record_learning_event(
            user=self.user,
            skill_code=another.code,
            event_type="assessment_answer",
            source_type="assessment",
            source_id="2",
            idempotency_key="public-sharing-evidence-2",
            outcome=1,
        )
        share.refresh_from_db()
        self.assertEqual(share.snapshot_hash, original_hash)
        self.assertEqual(share.snapshot["observed_skill_count"], original_count)
        refreshed = refresh_public_share(self.user, share)
        self.assertNotEqual(refreshed.snapshot_hash, original_hash)
        self.assertEqual(refreshed.snapshot["observed_skill_count"], 2)

    def test_create_is_idempotent_until_revoked(self):
        first = self.create_passport_share()
        second = self.create_passport_share(display_name="Learning alias")
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.public_id, second.public_id)
        self.assertEqual(
            PublicShare.objects.filter(
                user=self.user,
                share_type="passport",
                is_active=True,
            ).count(),
            1,
        )
        self.assertEqual(second.display_name, "Learning alias")

    def test_public_page_is_noindex_no_store_and_identity_minimized(self):
        share = self.create_passport_share()
        response = self.client.get(
            reverse("intelligence:public_share", args=[share.public_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store, max-age=0")
        self.assertEqual(
            response["X-Robots-Tag"],
            "noindex, nofollow, noarchive",
        )
        self.assertContains(response, "CodeLabX learner")
        self.assertContains(response, "not identity verification")
        self.assertNotContains(response, self.user.username)
        self.assertNotContains(response, self.user.email)

    def test_revocation_returns_generic_410_without_owner_details(self):
        share = self.create_passport_share()
        revoke_public_share(self.user, share)
        response = self.client.get(
            reverse("intelligence:public_share", args=[share.public_id])
        )
        self.assertEqual(response.status_code, 410)
        self.assertContains(response, "was revoked", status_code=410)
        self.assertNotContains(response, self.user.username, status_code=410)
        self.assertNotContains(response, share.display_name, status_code=410)
        self.assertIn("no-store", response["Cache-Control"])

    def test_owner_actions_are_post_only_and_other_user_is_404(self):
        share = self.create_passport_share()
        refresh_url = reverse("intelligence:refresh_share", args=[share.id])
        revoke_url = reverse("intelligence:revoke_share", args=[share.id])
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(refresh_url).status_code, 405)
        self.assertEqual(self.client.get(revoke_url).status_code, 405)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(refresh_url).status_code, 404)
        self.assertEqual(self.client.post(revoke_url).status_code, 404)
        share.refresh_from_db()
        self.assertTrue(share.is_active)

    def test_dashboard_get_does_not_create_share_and_query_count_is_bounded(self):
        self.client.force_login(self.user)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("intelligence:sharing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Share only what you approve")
        self.assertFalse(PublicShare.objects.exists())
        self.assertLessEqual(
            len(queries),
            12,
            msg=f"Sharing dashboard exceeded query budget: {len(queries)}",
        )

    def test_create_endpoint_requires_confirmation_and_uses_generic_default(self):
        self.client.force_login(self.user)
        url = reverse("intelligence:create_passport_share")
        self.assertEqual(self.client.get(url).status_code, 405)
        rejected = self.client.post(
            url,
            {"display_name": "CodeLabX learner"},
        )
        self.assertEqual(rejected.status_code, 302)
        self.assertFalse(PublicShare.objects.exists())
        created = self.client.post(
            url,
            {
                "display_name": "CodeLabX learner",
                "include_evidence_counts": "on",
                "confirmation": "on",
            },
        )
        self.assertEqual(created.status_code, 302)
        self.assertEqual(PublicShare.objects.get().display_name, "CodeLabX learner")

    def test_model_rejects_cross_owner_and_mismatched_snapshot(self):
        with self.assertRaises(ValidationError):
            PublicShare.objects.create(
                user=self.other,
                share_type="roadmap",
                roadmap=self.roadmap,
                display_name="Other",
                snapshot={"kind": "roadmap"},
                snapshot_hash="a" * 64,
            )
        with self.assertRaises(ValidationError):
            PublicShare.objects.create(
                user=self.user,
                share_type="passport",
                display_name="Learner",
                snapshot={"kind": "roadmap"},
                snapshot_hash="a" * 64,
            )

    def test_account_export_contains_owned_share_snapshot(self):
        share = self.create_passport_share()
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:export_account_data"))
        data = json.loads(response.content)["learning_intelligence"]
        self.assertEqual(len(data["public_shares"]), 1)
        self.assertEqual(data["public_shares"][0]["public_id"], str(share.public_id))
        self.assertEqual(
            data["public_shares"][0]["snapshot_hash"],
            share.snapshot_hash,
        )

    def test_public_share_model_registered_and_engine_has_no_ai_dependency(self):
        self.assertIn(PublicShare, admin.site._registry)
        source = (
            Path(__file__).resolve().parent
            / "services"
            / "public_sharing.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Gemini", source)
        self.assertNotIn("ai_tools", source)
