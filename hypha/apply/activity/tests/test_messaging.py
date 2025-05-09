import hashlib
import hmac
import json
from unittest.mock import ANY, Mock, call, patch

import responses
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django_slack.utils import get_backend

from hypha.apply.funds.tests.factories import (
    ApplicationSubmissionFactory,
    AssignedReviewersFactory,
    AssignedWithRoleReviewersFactory,
)
from hypha.apply.projects.tests.factories import InvoiceFactory, ProjectFactory
from hypha.apply.review.tests.factories import ReviewFactory
from hypha.apply.users.tests.factories import (
    ApplicantFactory,
    PartnerFactory,
    ReviewerFactory,
    StaffFactory,
    UserFactory,
)
from hypha.apply.utils.testing import make_request

from ..adapters import ActivityAdapter, AdapterBase, EmailAdapter, SlackAdapter
from ..adapters.base import neat_related
from ..messaging import MessengerBackend
from ..models import (
    ALL,
    APPLICANT,
    APPLICANT_PARTNERS,
    PARTNER,
    TEAM,
    Activity,
    Event,
    Message,
)
from ..options import MESSAGES
from .factories import CommentFactory, EventFactory, MessageFactory


class Contains(str):
    """Class used to ensure a mocked call's arg contains a specific string"""

    def __eq__(self, other):
        return self in other


class NotContains(str):
    """Class used to ensure a mocked call's arg doesn't contain a specific string"""

    def __eq__(self, other):
        return self not in other


class TestAdapter(AdapterBase):
    """A test class which will pass the message type to send_message"""

    adapter_type = "Test Adapter"
    messages = {enum: enum.value for enum in MESSAGES.__members__.values()}

    def send_message(self, message, **kwargs):
        pass

    def recipients(self, message_type, **kwargs):
        return [message_type]

    def log_message(self, message, recipient, event, status):
        pass


class AdapterMixin(TestCase):
    adapter = None
    source_factory = None

    def process_kwargs(self, message_type, **kwargs):
        if "user" not in kwargs:
            kwargs["user"] = UserFactory()
        if "source" not in kwargs:
            kwargs["source"] = self.source_factory()
        if "request" not in kwargs:
            kwargs["request"] = make_request()
        if message_type in neat_related:
            kwargs["related"] = kwargs.get("related", "a thing")
        else:
            kwargs["related"] = None

        return kwargs

    def adapter_process(self, message_type, adapter=None, **kwargs):
        if not adapter:
            adapter = self.adapter
        kwargs = self.process_kwargs(message_type, **kwargs)
        event = EventFactory(source=kwargs["source"])
        adapter.process(message_type, event=event, **kwargs)


@override_settings(SEND_MESSAGES=True)
class TestBaseAdapter(AdapterMixin, TestCase):
    source_factory = ApplicationSubmissionFactory

    def setUp(self):
        patched_class = patch.object(TestAdapter, "send_message")
        self.mock_adapter = patched_class.start()
        self.adapter = TestAdapter()
        self.adapter.send_message.return_value = "dummy_message"
        self.addCleanup(patched_class.stop)

    def test_can_send_a_message(self):
        message_type = MESSAGES.UPDATE_LEAD
        self.adapter_process(message_type)

        self.adapter.send_message.assert_called_once()
        self.assertEqual(self.adapter.send_message.call_args[0], (message_type.value,))

    def test_doesnt_send_a_message_if_not_configured(self):
        self.adapter_process("this_is_not_a_message_type")

        self.adapter.send_message.assert_not_called()

    def test_calls_method_if_available(self):
        method_name = "new_method"
        return_message = "Returned message"
        setattr(self.adapter, method_name, lambda **kw: return_message)
        self.adapter.messages[method_name] = method_name

        self.adapter_process(method_name)

        self.adapter.send_message.assert_called_once()
        self.assertEqual(self.adapter.send_message.call_args[0], (return_message,))

    def test_that_kwargs_passed_to_send_message(self):
        message_type = MESSAGES.UPDATE_LEAD
        kwargs = {"test": "that", "these": "exist"}
        self.adapter_process(message_type, **kwargs)

        self.adapter.send_message.assert_called_once()
        for key in kwargs:
            self.assertTrue(key in self.adapter.send_message.call_args[1])

    def test_that_message_is_formatted(self):
        message_type = MESSAGES.UPDATE_LEAD
        message = "message value"

        with patch.dict(self.adapter.messages, {message_type: "{message_to_format}"}):
            self.adapter_process(message_type, message_to_format=message)

        self.adapter.send_message.assert_called_once()
        self.assertEqual(self.adapter.send_message.call_args[0], (message,))

    def test_can_include_extra_kwargs(self):
        message_type = MESSAGES.UPDATE_LEAD

        with patch.dict(self.adapter.messages, {message_type: "{extra}"}):
            with patch.object(
                self.adapter, "extra_kwargs", return_value={"extra": "extra"}
            ):
                self.adapter_process(message_type)

        self.adapter.send_message.assert_called_once()
        self.assertTrue("extra" in self.adapter.send_message.call_args[1])

    @override_settings(SEND_MESSAGES=False)
    def test_django_messages_used(self):
        request = make_request()
        self.adapter_process(MESSAGES.UPDATE_LEAD, request=request)

        messages = list(get_messages(request))
        assert len(messages) == 1
        assert MESSAGES.UPDATE_LEAD.value in messages[0].message
        assert self.adapter.adapter_type in messages[0].message


class TestMessageBackendApplication(TestCase):
    source_factory = ApplicationSubmissionFactory

    def setUp(self):
        self.mocked_adapter = Mock(AdapterBase)
        self.backend = MessengerBackend
        self.kwargs = {
            "related": None,
            "request": None,
            "user": UserFactory(),
            "source": self.source_factory(),
        }

    def test_message_sent_to_adapter(self):
        adapter = self.mocked_adapter()
        messenger = self.backend(adapter)

        messenger(MESSAGES.UPDATE_LEAD, **self.kwargs)

        adapter.process.assert_called_once_with(
            MESSAGES.UPDATE_LEAD, Event.objects.first(), **self.kwargs
        )

    def test_message_sent_to_all_adapter(self):
        adapters = [self.mocked_adapter(), self.mocked_adapter()]
        messenger = self.backend(*adapters)

        messenger(MESSAGES.UPDATE_LEAD, **self.kwargs)

        adapter = adapters[0]
        self.assertEqual(adapter.process.call_count, len(adapters))

    def test_event_created(self):
        adapters = [self.mocked_adapter(), self.mocked_adapter()]
        messenger = self.backend(*adapters)
        user = UserFactory()
        self.kwargs.update(user=user)

        messenger(MESSAGES.UPDATE_LEAD, **self.kwargs)

        self.assertEqual(Event.objects.count(), 1)
        self.assertEqual(Event.objects.first().type, MESSAGES.UPDATE_LEAD.name)
        self.assertEqual(
            Event.objects.first().get_type_display(), MESSAGES.UPDATE_LEAD.label
        )
        self.assertEqual(Event.objects.first().by, user)


class TestMessageBackendProject(TestMessageBackendApplication):
    source_factory = ProjectFactory


@override_settings(SEND_MESSAGES=True)
class TestActivityAdapter(TestCase):
    def setUp(self):
        self.adapter = ActivityAdapter()

    def test_activity_created(self):
        message = "test message"
        user = UserFactory()
        submission = ApplicationSubmissionFactory()

        self.adapter.send_message(
            message,
            user=user,
            source=submission,
            sources=[],
            related=None,
        )

        self.assertEqual(Activity.objects.count(), 1)
        activity = Activity.objects.first()
        self.assertEqual(activity.user, user)
        self.assertEqual(activity.message, message)
        self.assertEqual(activity.source, submission)

    def test_reviewers_message_no_removed(self):
        assigned_reviewer = AssignedReviewersFactory()

        message = self.adapter.reviewers_updated([assigned_reviewer], [])

        self.assertTrue("Added" in message)
        self.assertFalse("Removed" in message)
        self.assertTrue(str(assigned_reviewer.reviewer) in message)

    def test_reviewers_message_no_added(self):
        assigned_reviewer = AssignedReviewersFactory()
        message = self.adapter.reviewers_updated([], [assigned_reviewer])

        self.assertFalse("Added" in message)
        self.assertTrue("Removed" in message)
        self.assertTrue(str(assigned_reviewer.reviewer) in message)

    def test_reviewers_message_both(self):
        added, removed = AssignedReviewersFactory.create_batch(2)
        message = self.adapter.reviewers_updated([added], [removed])

        self.assertTrue("Added" in message)
        self.assertTrue("Removed" in message)
        self.assertTrue(str(added.reviewer) in message)
        self.assertTrue(str(removed.reviewer) in message)

    def test_reviewers_with_role(self):
        with_role = AssignedWithRoleReviewersFactory()
        message = self.adapter.reviewers_updated([with_role], [])
        self.assertTrue(str(with_role.reviewer) in message)
        self.assertTrue(str(with_role.role) in message)

    def test_reviewers_with_and_without_role(self):
        with_role = AssignedWithRoleReviewersFactory()
        without_role = AssignedReviewersFactory()
        message = self.adapter.reviewers_updated([with_role, without_role], [])
        self.assertTrue(str(with_role.reviewer) in message)
        self.assertTrue(str(with_role.role) in message)
        self.assertTrue(str(without_role.reviewer) in message)

    def test_internal_transition_kwarg_for_invisible_transition(self):
        submission = ApplicationSubmissionFactory(status="post_review_discussion")
        kwargs = self.adapter.extra_kwargs(
            MESSAGES.TRANSITION, source=submission, sources=None
        )

        self.assertEqual(kwargs["visibility"], TEAM)

    def test_public_transition_kwargs(self):
        submission = ApplicationSubmissionFactory()
        kwargs = self.adapter.extra_kwargs(
            MESSAGES.TRANSITION, source=submission, sources=None
        )

        self.assertNotIn("visibility", kwargs)

    def test_handle_transition_public_to_public(self):
        submission = ApplicationSubmissionFactory(status="more_info")
        old_phase = submission.workflow.phases_for()[0]

        message = self.adapter.handle_transition(old_phase, submission)
        message = json.loads(message)

        self.assertIn(submission.phase.display_name, message[TEAM])
        self.assertIn(old_phase.display_name, message[TEAM])
        self.assertIn(submission.phase.public_name, message[ALL])
        self.assertIn(old_phase.public_name, message[ALL])

    def test_handle_transition_to_private_to_public(self):
        submission = ApplicationSubmissionFactory(status="more_info")
        old_phase = submission.workflow.phases_for()[1]

        message = self.adapter.handle_transition(old_phase, submission)
        message = json.loads(message)

        self.assertIn(submission.phase.display_name, message[TEAM])
        self.assertIn(old_phase.display_name, message[TEAM])
        self.assertIn(submission.phase.public_name, message[ALL])
        self.assertIn(old_phase.public_name, message[ALL])

    def test_handle_transition_to_public_to_private(self):
        submission = ApplicationSubmissionFactory(status="internal_review")
        old_phase = submission.workflow.phases_for()[0]

        message = self.adapter.handle_transition(old_phase, submission)

        self.assertIn(submission.phase.display_name, message)
        self.assertIn(old_phase.display_name, message)

    def test_lead_saved_on_activity(self):
        submission = ApplicationSubmissionFactory()
        user = UserFactory()
        self.adapter.send_message(
            "a message", user=user, source=submission, sources=[], related=user
        )
        activity = Activity.objects.first()
        self.assertEqual(activity.related_object, user)

    def test_review_saved_on_activity(self):
        review = ReviewFactory()
        self.adapter.send_message(
            "a message",
            user=review.author.reviewer,
            source=review.submission,
            sources=[],
            related=review,
        )
        activity = Activity.objects.first()
        self.assertEqual(activity.related_object, review)


class TestSlackAdapter(AdapterMixin, TestCase):
    source_factory = ApplicationSubmissionFactory

    backend = "django_slack.backends.TestBackend"
    target_url = "https://my-slack-backend.com/incoming/my-very-secret-key"
    target_room = "#<ROOM ID>"
    token = "fake-token"

    @override_settings(
        SLACK_ENDPOINT_URL=target_url,
        SLACK_DESTINATION_ROOM=None,
        SLACK_BACKEND=backend,
        SLACK_TOKEN=token,
    )
    def test_cant_send_with_no_room(self):
        error_message = "Missing configuration: Room ID"
        adapter = SlackAdapter()
        submission = ApplicationSubmissionFactory()
        messages = adapter.send_message("my message", "", source=submission)
        self.assertEqual(messages, error_message)

    @override_settings(
        SLACK_ENDPOINT_URL=target_url,
        SLACK_DESTINATION_ROOM=target_room,
        SLACK_BACKEND=backend,
        SLACK_TOKEN=None,
    )
    def test_cant_send_with_no_token(self):
        error_message = "Missing configuration: Slack Token"
        adapter = SlackAdapter()
        submission = ApplicationSubmissionFactory()
        messages = adapter.send_message("my message", "", source=submission)
        self.assertEqual(messages, error_message)

    @override_settings(
        SLACK_ENDPOINT_URL=target_url,
        SLACK_DESTINATION_ROOM=target_room,
        SLACK_BACKEND=backend,
        SLACK_TOKEN=token,
    )
    def test_correct_payload(self):
        backend = get_backend()
        backend.reset_messages()
        submission = ApplicationSubmissionFactory()
        adapter = SlackAdapter()
        message = "my message"
        adapter.send_message(message, "", source=submission)
        messages = backend.retrieve_messages()
        self.assertEqual(len(messages), 1)
        message_payload = json.loads(messages[0]["payload"])
        self.assertEqual(message_payload["text"], message)

    @override_settings(
        SLACK_ENDPOINT_URL=target_url,
        SLACK_DESTINATION_ROOM=target_room,
        SLACK_BACKEND=backend,
        SLACK_TOKEN=token,
    )
    def test_fund_custom_slack_channel(self):
        backend = get_backend()
        backend.reset_messages()
        responses.add(responses.POST, self.target_url, status=200, body="OK")
        submission = ApplicationSubmissionFactory(round__parent__slack_channel="dummy")
        adapter = SlackAdapter()
        message = "my message"
        adapter.send_message(message, "", source=submission)
        messages = backend.retrieve_messages()
        self.assertEqual(len(messages), 1)
        message_payload = json.loads(messages[0]["payload"])
        self.assertEqual(message_payload["text"], message)
        self.assertEqual(message_payload["channel"], "#dummy")

    @override_settings(
        SLACK_ENDPOINT_URL=target_url,
        SLACK_DESTINATION_ROOM=target_room,
        SLACK_BACKEND=backend,
        SLACK_TOKEN=token,
    )
    def test_fund_multiple_custom_slack_channel(self):
        backend = get_backend()
        backend.reset_messages()
        submission = ApplicationSubmissionFactory(
            round__parent__slack_channel="dummy1, dummy2"
        )
        adapter = SlackAdapter()
        message = "my message"
        adapter.send_message(message, "", source=submission)
        messages = backend.retrieve_messages()
        self.assertEqual(len(messages), 2)
        for index, sent_message in enumerate(messages):
            message_payload = json.loads(sent_message["payload"])
            self.assertEqual(message_payload["text"], message)
            self.assertEqual(message_payload["channel"], "#dummy" + str(index + 1))

    def test_gets_lead_if_slack_set(self):
        adapter = SlackAdapter()
        submission = ApplicationSubmissionFactory()
        recipients = adapter.recipients(
            MESSAGES.COMMENT, source=submission, related=None
        )
        self.assertTrue(submission.lead.slack in recipients[0])

    def test_gets_blank_if_slack_not_set(self):
        adapter = SlackAdapter()
        submission = ApplicationSubmissionFactory(lead__slack="")
        recipients = adapter.recipients(
            MESSAGES.COMMENT, source=submission, related=None
        )
        self.assertTrue(submission.lead.slack in recipients[0])

    @override_settings(
        SLACK_ENDPOINT_URL=target_url,
        SLACK_DESTINATION_ROOM=target_room,
        SLACK_BACKEND=backend,
        SLACK_TOKEN=token,
    )
    def test_message_with_good_response(self):
        self.adapter = SlackAdapter()
        self.adapter_process(MESSAGES.NEW_SUBMISSION)
        self.assertEqual(Message.objects.count(), 1)
        sent_message = Message.objects.first()
        self.assertEqual(
            sent_message.content[0:10],
            self.adapter.messages[MESSAGES.NEW_SUBMISSION][0:10],
        )
        self.assertEqual(sent_message.status, "200: OK")

    @override_settings(
        SLACK_ENDPOINT_URL=target_url,
        SLACK_DESTINATION_ROOM=target_room,
        SLACK_BACKEND=backend,
        SLACK_TOKEN=token,
    )
    def test_400_bad_request(self):
        backend = get_backend()
        backend.reset_messages()
        submission = ApplicationSubmissionFactory()
        adapter = SlackAdapter()
        message = ""
        message_status = adapter.send_message(message, "", source=submission)
        messages = backend.retrieve_messages()
        self.assertEqual(len(messages), 0)
        self.assertEqual(message_status, "400: Bad Request")


@override_settings(SEND_MESSAGES=True)
class TestEmailAdapter(AdapterMixin, TestCase):
    source_factory = ApplicationSubmissionFactory
    adapter = EmailAdapter()

    def setUp(self):
        patched_send_mail = patch("hypha.apply.activity.tasks.send_mail")
        self.mock_send_email = patched_send_mail.start()
        self.addCleanup(patched_send_mail.stop)

    def test_email_new_submission(self):
        submission = ApplicationSubmissionFactory()
        self.adapter_process(MESSAGES.NEW_SUBMISSION, source=submission)

        self.mock_send_email.assert_called_once_with(
            ANY, ANY, ANY, [submission.user.email], logs=ANY
        )

    def test_no_email_private_comment(self):
        comment = CommentFactory(internal=True)

        self.adapter_process(MESSAGES.COMMENT, related=comment, source=comment.source)
        self.mock_send_email.assert_not_called()

    def test_no_email_own_submission_comment(self):
        submission = ApplicationSubmissionFactory()
        comment = CommentFactory(user=submission.user, source=submission)

        self.adapter_process(
            MESSAGES.COMMENT, related=comment, user=comment.user, source=comment.source
        )
        self.mock_send_email.assert_not_called()

    def test_no_email_own_project_comment(self):
        project = ProjectFactory()
        comment = CommentFactory(user=project.user, source=project)

        self.adapter_process(
            MESSAGES.COMMENT, related=comment, user=comment.user, source=comment.source
        )
        self.mock_send_email.assert_not_called()

    def test_email_staff_submission_comments(self):
        staff_commenter = StaffFactory()
        submission = ApplicationSubmissionFactory()
        comment = CommentFactory(
            user=staff_commenter, source=submission, visibility=APPLICANT
        )

        self.adapter_process(
            MESSAGES.COMMENT, related=comment, user=comment.user, source=comment.source
        )
        self.mock_send_email.assert_called_once_with(
            ANY, ANY, ANY, [submission.user.email], logs=ANY
        )

    def test_email_staff_project_comments(self):
        staff_commenter = StaffFactory()
        project = ProjectFactory()
        comment = CommentFactory(
            user=staff_commenter, source=project, visibility=APPLICANT
        )

        self.adapter_process(
            MESSAGES.COMMENT, related=comment, user=comment.user, source=comment.source
        )

        self.mock_send_email.assert_called_once_with(
            ANY, ANY, ANY, [project.user.email], logs=ANY
        )

    def test_email_partner_for_submission_comments(self):
        partners = PartnerFactory.create_batch(2)
        submission = ApplicationSubmissionFactory()
        submission.partners.set(partners)
        comment = CommentFactory(
            user=submission.user, source=submission, visibility=PARTNER
        )

        self.adapter_process(
            MESSAGES.COMMENT, related=comment, user=comment.user, source=comment.source
        )

        partner_emails = [partner.email for partner in partners]

        calls = [call(ANY, ANY, ANY, [email], logs=ANY) for email in partner_emails]

        self.mock_send_email.assert_has_calls(calls, any_order=True)

    def test_email_applicant_partners_for_submission_comments(self):
        staff_commenter = StaffFactory()
        partners = PartnerFactory.create_batch(2)
        submission = ApplicationSubmissionFactory()
        submission.partners.set(partners)
        comment = CommentFactory(
            user=staff_commenter, source=submission, visibility=APPLICANT_PARTNERS
        )

        self.adapter_process(
            MESSAGES.COMMENT, related=comment, user=comment.user, source=comment.source
        )

        applicant_partner_emails = [partner.email for partner in partners] + [
            submission.user.email
        ]

        calls = [
            call(ANY, ANY, ANY, [email], logs=ANY) for email in applicant_partner_emails
        ]

        self.mock_send_email.assert_has_calls(calls, any_order=True)

    def test_email_applicant_for_submission_comments(self):
        staff_commenter = StaffFactory()
        partners = PartnerFactory.create_batch(2)
        submission = ApplicationSubmissionFactory()
        submission.partners.set(partners)
        comment = CommentFactory(
            user=staff_commenter, source=submission, visibility=APPLICANT
        )

        self.adapter_process(
            MESSAGES.COMMENT, related=comment, user=comment.user, source=comment.source
        )

        self.mock_send_email.assert_called_once_with(
            ANY, ANY, ANY, [submission.user.email], logs=ANY
        )

    def test_reviewers_email(self):
        reviewers = ReviewerFactory.create_batch(4)
        submission = ApplicationSubmissionFactory(
            status="external_review", reviewers=reviewers, workflow_stages=2
        )
        self.adapter_process(MESSAGES.READY_FOR_REVIEW, source=submission)

        reviewer_emails = [reviewer.email for reviewer in reviewers]

        calls = [
            call(Contains("ready to review"), ANY, ANY, [email], logs=ANY)
            for email in reviewer_emails
        ]

        self.mock_send_email.assert_has_calls(calls, any_order=True)

    def test_reviewer_update_email(self):
        reviewers = ReviewerFactory.create_batch(4)
        submission = ApplicationSubmissionFactory(
            status="external_review", reviewers=reviewers, workflow_stages=2
        )
        added = [AssignedReviewersFactory(submission=submission, reviewer=reviewers[0])]
        self.adapter_process(MESSAGES.REVIEWERS_UPDATED, source=submission, added=added)

        reviewer_emails = [user.reviewer.email for user in added]

        self.mock_send_email.assert_called_once_with(
            Contains("ready to review"), ANY, ANY, reviewer_emails, logs=ANY
        )

    @override_settings(HIDE_STAFF_IDENTITY=True)
    def test_hide_staff_in_email(self):
        staff_commenter = StaffFactory()
        submission = ApplicationSubmissionFactory()
        comment = CommentFactory(
            user=staff_commenter, source=submission, visibility=APPLICANT
        )

        self.adapter_process(
            MESSAGES.COMMENT, related=comment, user=comment.user, source=comment.source
        )

        self.mock_send_email.assert_called_once_with(
            ANY,
            NotContains(str(staff_commenter)),
            ANY,
            [submission.user.email],
            logs=ANY,
        )

    def test_show_staff_in_email(self):
        staff_commenter = StaffFactory()
        submission = ApplicationSubmissionFactory()
        comment = CommentFactory(
            user=staff_commenter, source=submission, visibility=APPLICANT
        )

        self.adapter_process(
            MESSAGES.COMMENT, related=comment, user=comment.user, source=comment.source
        )

        self.mock_send_email.assert_called_once_with(
            ANY, Contains(str(staff_commenter)), ANY, [submission.user.email], logs=ANY
        )


@override_settings(
    SEND_MESSAGES=True,
    EMAIL_BACKEND="anymail.backends.test.EmailBackend",
)
class TestAnyMailBehaviour(AdapterMixin, TestCase):
    adapter = EmailAdapter()
    TEST_API_KEY = "TEST_API_KEY"

    def setUp(self):
        patched_send_mail = patch("hypha.apply.activity.tasks.send_mail")
        self.mock_send_email = patched_send_mail.start()
        self.addCleanup(patched_send_mail.stop)

    # from: https://github.com/anymail/django-anymail/blob/7d8dbdace92d8addfcf0a517be0aaf481da11952/tests/test_mailgun_webhooks.py#L19
    def mailgun_sign(self, data, api_key=TEST_API_KEY):
        """Add a Mailgun webhook signature to data dict"""
        # Modifies the dict in place
        data.setdefault("timestamp", "1234567890")
        data.setdefault("token", "1234567890abcdef1234567890abcdef")
        data["signature"] = hmac.new(
            key=api_key.encode("ascii"),
            msg="{timestamp}{token}".format(**data).encode("ascii"),
            digestmod=hashlib.sha256,
        ).hexdigest()

        return data

    def test_email_new_submission(self):
        submission = ApplicationSubmissionFactory()
        self.adapter_process(MESSAGES.NEW_SUBMISSION, source=submission)

        self.mock_send_email.assert_called_once_with(
            ANY, ANY, ANY, [submission.user.email], logs=ANY
        )

    @override_settings(ANYMAIL_MAILGUN_API_KEY=TEST_API_KEY)
    def test_webhook_updates_status(self):
        message = MessageFactory()
        response = self.client.post(
            "/activity/anymail/mailgun/tracking/",
            data=self.mailgun_sign(
                {"event": "delivered", "Message-Id": message.external_id}
            ),
            secure=True,
            json=True,
        )
        self.assertEqual(response.status_code, 200)
        message.refresh_from_db()
        self.assertTrue("delivered" in message.status)

    @override_settings(ANYMAIL_MAILGUN_API_KEY=TEST_API_KEY)
    def test_webhook_adds_reject_reason(self):
        message = MessageFactory()
        response = self.client.post(
            "/activity/anymail/mailgun/tracking/",
            data=self.mailgun_sign(
                {
                    "event": "dropped",
                    "reason": "hardfail",
                    "code": 607,
                    "description": "Marked as spam",
                    "Message-Id": message.external_id,
                }
            ),
            secure=True,
            json=True,
        )
        self.assertEqual(response.status_code, 200)
        message.refresh_from_db()
        self.assertTrue("rejected" in message.status)
        self.assertTrue("spam" in message.status)


class TestAdaptersForProject(AdapterMixin, TestCase):
    slack = SlackAdapter
    activity = ActivityAdapter
    source_factory = ProjectFactory
    # Slack
    backend = "django_slack.backends.TestBackend"
    target_url = "https://my-slack-backend.com/incoming/my-very-secret-key"
    target_room = "#<ROOM ID>"
    token = "fake-token"

    def test_activity_lead_change(self):
        old_lead = UserFactory()
        project = self.source_factory()
        self.adapter_process(
            MESSAGES.UPDATE_PROJECT_LEAD,
            adapter=self.activity(),
            source=project,
            related=old_lead,
        )
        self.assertEqual(Activity.objects.count(), 1)
        activity = Activity.objects.first()
        self.assertIn(str(old_lead), activity.message)
        self.assertIn(str(project.lead), activity.message)

    def test_activity_lead_change_from_none(self):
        project = self.source_factory()
        self.adapter_process(
            MESSAGES.UPDATE_PROJECT_LEAD,
            adapter=self.activity(),
            source=project,
            related="Unassigned",
        )
        self.assertEqual(Activity.objects.count(), 1)
        activity = Activity.objects.first()
        self.assertIn(str("Unassigned"), activity.message)
        self.assertIn(str(project.lead), activity.message)

    def test_activity_created(self):
        project = self.source_factory()
        self.adapter_process(
            MESSAGES.CREATED_PROJECT,
            adapter=self.activity(),
            source=project,
            related=project.submission,
            status="Draft",
        )
        self.assertEqual(Activity.objects.count(), 1)
        activity = Activity.objects.first()
        self.assertEqual(project.submission, activity.related_object)

    @override_settings(
        SLACK_ENDPOINT_URL=target_url,
        SLACK_DESTINATION_ROOM=target_room,
        SLACK_BACKEND=backend,
        SLACK_TOKEN=token,
    )
    def test_slack_created(self):
        backend = get_backend()
        backend.reset_messages()
        project = self.source_factory()
        user = UserFactory()
        self.adapter_process(
            MESSAGES.CREATED_PROJECT,
            adapter=self.slack(),
            user=user,
            source=project,
            related=project.submission,
        )
        messages = backend.retrieve_messages()
        self.assertEqual(len(messages), 1)
        message_payload = json.loads(messages[0]["payload"])
        self.assertIn(str(user), message_payload["text"])
        self.assertIn(str(project), message_payload["text"])

    @override_settings(
        SLACK_ENDPOINT_URL=target_url,
        SLACK_DESTINATION_ROOM=target_room,
        SLACK_BACKEND=backend,
        SLACK_TOKEN=token,
    )
    def test_slack_lead_change(self):
        backend = get_backend()
        backend.reset_messages()
        project = self.source_factory()
        user = UserFactory()
        self.adapter_process(
            MESSAGES.UPDATE_PROJECT_LEAD,
            adapter=self.slack(),
            user=user,
            source=project,
            related=project.submission,
        )
        messages = backend.retrieve_messages()
        self.assertEqual(len(messages), 1)
        message_payload = json.loads(messages[0]["payload"])
        self.assertIn(str(user), message_payload["text"])
        self.assertIn(str(project), message_payload["text"])

    @override_settings(
        SLACK_ENDPOINT_URL=target_url,
        SLACK_DESTINATION_ROOM=target_room,
        SLACK_BACKEND=backend,
        SLACK_TOKEN=token,
    )
    def test_slack_applicant_update_invoice(self):
        backend = get_backend()
        backend.reset_messages()
        project = self.source_factory()
        invoice = InvoiceFactory(project=project)
        applicant = ApplicantFactory()

        self.adapter_process(
            MESSAGES.UPDATE_INVOICE,
            adapter=self.slack(),
            user=applicant,
            source=project,
            related=invoice,
        )
        messages = backend.retrieve_messages()

        self.assertEqual(len(messages), 1)
        message_payload = json.loads(messages[0]["payload"])
        self.assertIn(str(applicant), message_payload["text"])
        self.assertIn(str(project), message_payload["text"])

    @override_settings(
        SLACK_ENDPOINT_URL=target_url,
        SLACK_DESTINATION_ROOM=target_room,
        SLACK_BACKEND=backend,
        SLACK_TOKEN=token,
    )
    def test_slack_staff_update_invoice(self):
        backend = get_backend()
        backend.reset_messages()
        project = self.source_factory()
        invoice = InvoiceFactory(project=project)
        staff = StaffFactory()

        self.adapter_process(
            MESSAGES.UPDATE_INVOICE,
            adapter=self.slack(),
            user=staff,
            source=project,
            related=invoice,
        )
        messages = backend.retrieve_messages()
        self.assertEqual(len(messages), 1)

    @override_settings(SEND_MESSAGES=True)
    @patch("hypha.apply.activity.tasks.send_mail")
    def test_email_staff_update_invoice(self, mock_send_email):
        project = self.source_factory()
        invoice = InvoiceFactory(project=project)
        staff = StaffFactory()

        self.adapter_process(
            MESSAGES.UPDATE_INVOICE,
            adapter=EmailAdapter(),
            user=staff,
            source=project,
            related=invoice,
        )

        mock_send_email.assert_called_once_with(
            ANY, ANY, ANY, [project.user.email], logs=ANY
        )
