import json
from io import BytesIO

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from hypha.apply.funds.tests.factories import LabSubmissionFactory
from hypha.apply.projects.utils import get_invoice_status_display_value
from hypha.apply.users.tests.factories import (
    ApplicantFactory,
    ApproverFactory,
    ContractingFactory,
    FinanceFactory,
    ReviewerFactory,
    StaffFactory,
    SuperUserFactory,
    UserFactory,
)
from hypha.apply.utils.testing.tests import BaseViewTestCase
from hypha.home.factories import ApplySiteFactory

from ..forms import SetPendingForm
from ..models.payment import CHANGES_REQUESTED_BY_STAFF, DECLINED, SUBMITTED
from ..models.project import (
    APPROVE,
    CONTRACTING,
    DRAFT,
    INTERNAL_APPROVAL,
    INVOICING_AND_REPORTING,
    REQUEST_CHANGE,
    ProjectSettings,
)
from ..views.project import ContractsMixin, ProjectDetailApprovalView
from .factories import (
    ContractFactory,
    DocumentCategoryFactory,
    InvoiceFactory,
    PacketFileFactory,
    PAFApprovalsFactory,
    PAFReviewerRoleFactory,
    ProjectFactory,
    SupportingDocumentFactory,
)

# A boilerplate stream form for Project Report tests below.
FORM_FIELDS = [
    {
        "id": "012a4f29-0882-4b1c-b567-aede1b601d4a",
        "type": "number",
        "value": {
            "required": True,
            "help_text": "",
            "field_label": "How many folks did you reach?",
            "default_value": "",
        },
    }
]


class TestUpdateLeadView(BaseViewTestCase):
    base_view_name = "detail"
    url_name = "funds:projects:{}"
    user_factory = ApproverFactory

    def get_kwargs(self, instance):
        return {"pk": instance.submission.id}

    def test_update_lead(self):
        project = ProjectFactory()

        new_lead = self.user_factory()
        response = self.post_page(
            project, {"lead": new_lead.id}, view_name="lead_update"
        )
        self.assertEqual(response.status_code, 204)

        project.refresh_from_db()
        self.assertEqual(project.lead, new_lead)

    def test_update_lead_from_none(self):
        project = ProjectFactory(lead=None)

        new_lead = self.user_factory()
        response = self.post_page(
            project,
            {"lead": new_lead.id},
            view_name="lead_update",
        )
        self.assertEqual(response.status_code, 204)

        project.refresh_from_db()
        self.assertEqual(project.lead, new_lead)


class TestSendForApprovalView(BaseViewTestCase):
    base_view_name = "detail"
    url_name = "funds:projects:{}"
    user_factory = StaffFactory

    def setUp(self):
        super().setUp()
        apply_site = ApplySiteFactory()
        self.project_setting, _ = ProjectSettings.objects.get_or_create(
            site_id=apply_site.id
        )
        self.project_setting.use_settings = True
        self.project_setting.save()
        self.role = PAFReviewerRoleFactory(page=self.project_setting)

    def get_kwargs(self, instance):
        return {"pk": instance.submission.id}

    def test_send_for_approval_fails_when_project_is_locked(self):
        project = ProjectFactory(is_locked=True)

        # The view doesn't have any custom changes when form validation fails
        # so check that directly.
        form = SetPendingForm(instance=project)
        self.assertFalse(form.is_valid())

    def test_send_for_approval_fails_when_project_is_not_in_draft_state(self):
        project = ProjectFactory(status=INVOICING_AND_REPORTING)

        # The view doesn't have any custom changes when form validation fails
        # so check that directly.
        form = SetPendingForm(instance=project)
        self.assertFalse(form.is_valid())

    def test_send_for_approval_happy_path(self):
        project = ProjectFactory(is_locked=False, status=DRAFT)

        response = self.post_page(project, {}, view_name="submit_project_for_approval")
        self.assertEqual(response.status_code, 200)

        project.refresh_from_db()

        self.assertFalse(project.is_locked)
        self.assertEqual(project.status, INTERNAL_APPROVAL)


class TestChangePAFStatusView(BaseViewTestCase):
    base_view_name = "detail"
    url_name = "funds:projects:{}"
    user_factory = ApproverFactory

    def setUp(self):
        super().setUp()
        apply_site = ApplySiteFactory()
        self.project_setting, _ = ProjectSettings.objects.get_or_create(
            site_id=apply_site.id
        )
        self.project_setting.use_settings = True
        self.project_setting.save()
        self.role = PAFReviewerRoleFactory(page=self.project_setting)

    def get_kwargs(self, instance):
        return {"pk": instance.submission.id}

    def test_unassigned_applicant_cant_update_paf_status(self):
        user = ApplicantFactory()
        self.client.force_login(user=user)
        project = ProjectFactory(status=INTERNAL_APPROVAL)

        PAFApprovalsFactory(
            project=project, user=ApplicantFactory(), paf_reviewer_role=self.role
        )

        response = self.post_page(
            project, {"form-submitted-change_paf_status": "", "paf_status": APPROVE}
        )
        self.assertEqual(response.status_code, 403)

    def test_unassigned_staff_cant_update_paf_status(self):
        user = StaffFactory()
        self.client.force_login(user=user)
        project = ProjectFactory(status=INTERNAL_APPROVAL)

        PAFApprovalsFactory(
            project=project, user=StaffFactory(), paf_reviewer_role=self.role
        )

        response = self.post_page(
            project, {"paf_status": APPROVE}, view_name="update_pafstatus"
        )
        self.assertEqual(response.status_code, 403)

    def test_unassigned_finance_cant_update_paf_status(self):
        user = FinanceFactory()
        self.client.force_login(user=user)
        project = ProjectFactory(status=INTERNAL_APPROVAL)

        PAFApprovalsFactory(
            project=project, user=FinanceFactory(), paf_reviewer_role=self.role
        )

        response = self.post_page(
            project, {"paf_status": APPROVE}, view_name="update_pafstatus"
        )
        self.assertEqual(response.status_code, 403)

    def test_unassigned_contracting_cant_update_paf_status(self):
        user = ContractingFactory()
        self.client.force_login(user=user)
        project = ProjectFactory(status=INTERNAL_APPROVAL)

        PAFApprovalsFactory(
            project=project, user=ContractingFactory(), paf_reviewer_role=self.role
        )

        response = self.post_page(
            project,
            {"paf_status": APPROVE},
            view_name="update_pafstatus",
        )
        self.assertEqual(response.status_code, 403)

    def test_assigned_approvers_can_approve_paf(self):
        # reviewer can be staff, finance or contracting
        project = ProjectFactory(status=INTERNAL_APPROVAL)

        approval = PAFApprovalsFactory(
            project=project, user=self.user, paf_reviewer_role=self.role
        )

        response = self.post_page(
            project,
            {"paf_status": APPROVE},
            view_name="update_pafstatus",
        )

        self.assertEqual(response.status_code, 200)

        approval.refresh_from_db()
        project.refresh_from_db()
        self.assertEqual(self.role.label, approval.paf_reviewer_role.label)
        self.assertTrue(approval.approved)
        self.assertIn(approval, project.paf_approvals.filter(approved=True))

    def test_assigned_approvers_can_reject_paf(self):
        # reviewer can be staff, finance or contracting, or any assigned role
        project = ProjectFactory(status=INTERNAL_APPROVAL)

        approval = PAFApprovalsFactory(
            project=project, user=self.user, paf_reviewer_role=self.role
        )

        response = self.post_page(
            project,
            {"paf_status": REQUEST_CHANGE},
            view_name="update_pafstatus",
        )

        self.assertEqual(response.status_code, 200)
        project.refresh_from_db()
        self.assertEqual(project.status, DRAFT)
        approval.refresh_from_db()
        self.assertEqual(self.role.label, approval.paf_reviewer_role.label)
        self.assertFalse(approval.approved)
        self.assertIn(approval, project.paf_approvals.filter(approved=False))


class BaseProjectDetailTestCase(BaseViewTestCase):
    url_name = "funds:projects:{}"
    base_view_name = "detail"

    def get_kwargs(self, instance):
        return {"pk": instance.submission.id}


class TestApplicantProjectDetailView(BaseProjectDetailTestCase):
    user_factory = ApplicantFactory

    def test_has_access(self):
        project = ProjectFactory(user=self.user)
        response = self.get_page(project)
        self.assertEqual(response.status_code, 200)

    def test_lab_project_renders(self):
        project = ProjectFactory(user=self.user, submission=LabSubmissionFactory())
        response = self.get_page(project)
        self.assertEqual(response.status_code, 200)

    @override_settings(HIDE_STAFF_IDENTITY=True)
    def test_applicant_cant_see_hidden_lead(self):
        lead = StaffFactory()
        project = ProjectFactory(user=self.user, lead=lead)
        response = self.get_page(project)
        self.assertNotContains(response, str(lead))

    def test_applicant_can_see_lead(self):
        lead = StaffFactory()
        project = ProjectFactory(user=self.user, lead=lead)
        response = self.get_page(project, view_name="project_lead")
        self.assertContains(response, str(lead))


class TestStaffProjectDetailView(BaseProjectDetailTestCase):
    user_factory = StaffFactory

    def test_has_access(self):
        project = ProjectFactory()
        response = self.get_page(project)
        self.assertEqual(response.status_code, 200)

    def test_lab_project_renders(self):
        project = ProjectFactory(submission=LabSubmissionFactory())
        response = self.get_page(project)
        self.assertEqual(response.status_code, 200)


class TestFinanceProjectDetailView(BaseProjectDetailTestCase):
    user_factory = FinanceFactory

    def setUp(self):
        super().setUp()
        apply_site = ApplySiteFactory()
        self.project_setting, _ = ProjectSettings.objects.get_or_create(
            site_id=apply_site.id
        )
        self.project_setting.use_settings = True
        self.project_setting.save()
        self.role = PAFReviewerRoleFactory(page=self.project_setting)

    def test_has_access(self):
        project = ProjectFactory(status=INTERNAL_APPROVAL)
        response = self.get_page(project)
        self.assertEqual(response.status_code, 200)

    def test_lab_project_renders(self):
        project = ProjectFactory(
            submission=LabSubmissionFactory(), status=INTERNAL_APPROVAL
        )
        response = self.get_page(project)
        self.assertEqual(response.status_code, 200)


class TestUserProjectDetailView(BaseProjectDetailTestCase):
    user_factory = ApplicantFactory

    def test_doesnt_have_access(self):
        project = ProjectFactory()
        response = self.get_page(project)
        self.assertEqual(response.status_code, 403)

    def test_owner_has_access(self):
        project = ProjectFactory(user=self.user)
        response = self.get_page(project)
        self.assertEqual(response.status_code, 200)


class TestSuperUserProjectDetailView(BaseProjectDetailTestCase):
    user_factory = SuperUserFactory

    def test_has_access(self):
        project = ProjectFactory()
        response = self.get_page(project)
        self.assertEqual(response.status_code, 200)


class TestReviewerUserProjectDetailView(BaseProjectDetailTestCase):
    user_factory = ReviewerFactory

    def test_doesnt_have_access(self):
        project = ProjectFactory()
        response = self.get_page(project)
        self.assertEqual(response.status_code, 403)


class TestRemoveDocumentView(BaseViewTestCase):
    base_view_name = "detail"
    url_name = "funds:projects:{}"
    user_factory = StaffFactory

    def get_kwargs(self, instance):
        return {"pk": instance.submission.id}

    def test_remove_document(self):
        project = ProjectFactory()
        document = PacketFileFactory()

        response = self.post_page(
            project,
            {
                "form-submitted-remove_document_form": "",
                "id": document.id,
            },
        )
        project.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(document.pk, project.packet_files.values_list("pk", flat=True))

    def test_remove_non_existent_document(self):
        response = self.post_page(
            ProjectFactory(),
            {
                "form-submitted-remove_document_form": "",
                "id": 1,
            },
        )
        self.assertEqual(response.status_code, 200)


class TestApplicantUploadContractView(BaseViewTestCase):
    base_view_name = "detail"
    url_name = "funds:projects:{}"
    user_factory = ApplicantFactory

    def get_kwargs(self, instance):
        return {"pk": instance.submission.id}

    def test_owner_upload_contract(self):
        project = ProjectFactory(status=CONTRACTING, user=self.user)
        ContractFactory(project=project)

        test_doc = BytesIO(b"somebinarydata")
        test_doc.name = "contract.pdf"

        response = self.post_page(
            project,
            {
                "form-submitted-contract_form": "",
                "file": test_doc,
            },
        )
        self.assertEqual(response.status_code, 200)

        project.refresh_from_db()

        self.assertTrue(
            project.contracts.order_by("-created_at").first().signed_by_applicant
        )

    def test_non_owner_upload_contract(self):
        project = ProjectFactory(status=CONTRACTING)
        contract_count = project.contracts.count()

        test_doc = BytesIO(b"somebinarydata")
        test_doc.name = "test_contract.pdf"

        response = self.post_page(
            project,
            {
                "form-submitted-contract_form": "",
                "file": test_doc,
            },
        )
        self.assertEqual(response.status_code, 403)

        project.refresh_from_db()
        self.assertEqual(project.contracts.count(), contract_count)


class TestUploadDocumentView(BaseViewTestCase):
    base_view_name = "detail"
    url_name = "funds:projects:{}"
    user_factory = StaffFactory

    def setUp(self):
        super().setUp()
        self.category = DocumentCategoryFactory()

    def get_kwargs(self, instance):
        return {"pk": instance.submission.id, "category_pk": self.category.id}

    def test_upload_document(self):
        project = ProjectFactory()

        test_doc = BytesIO(b"somebinarydata")
        test_doc.name = "test_document.pdf"

        self.assertEqual(project.packet_files.count(), 0)

        response = self.post_page(
            project,
            {
                "title": "test document",
                "category": self.category.id,
                "document": test_doc,
            },
            view_name="supporting_doc_upload",
        )
        self.assertEqual(response.status_code, 204)

        project.refresh_from_db()

        self.assertEqual(project.packet_files.count(), 1)


class TestContractsMixin(TestCase):
    class DummyView:
        def get_context_data(self):
            return {}

    class DummyContractsView(ContractsMixin, DummyView):
        def __init__(self, project):
            self.project = project

        def get_object(self):
            return self.project

    def test_all_signed_and_approved_contracts_appear(self):
        project = ProjectFactory()
        user = StaffFactory()
        ContractFactory(project=project, signed_by_applicant=True, approver=user)
        ContractFactory(project=project, signed_by_applicant=True, approver=user)
        ContractFactory(project=project, signed_by_applicant=True, approver=user)

        contracts = self.DummyContractsView(project).get_context_data()["contracts"]

        self.assertEqual(len(contracts), 3)

    def test_mixture_with_latest_signed_returns_no_unsigned(self):
        project = ProjectFactory()
        user = StaffFactory()
        ContractFactory(project=project, signed_by_applicant=True, approver=user)
        ContractFactory(project=project, signed_by_applicant=False, approver=None)
        ContractFactory(project=project, signed_by_applicant=True, approver=user)

        contracts = self.DummyContractsView(project).get_context_data()["contracts"]

        self.assertEqual(len(contracts), 2)
        for contract in contracts:
            self.assertTrue(contract.signed_by_applicant)

    def test_no_contracts_returns_nothing(self):
        project = ProjectFactory()
        contracts = self.DummyContractsView(project).get_context_data()["contracts"]

        self.assertEqual(len(contracts), 0)

    def test_all_unsigned_and_unapproved_returns_only_latest(self):
        project = ProjectFactory()
        ContractFactory(project=project, signed_by_applicant=False, approver=None)
        ContractFactory(project=project, signed_by_applicant=False, approver=None)
        latest = ContractFactory(
            project=project, signed_by_applicant=False, approver=None
        )

        context = self.DummyContractsView(project).get_context_data()

        contracts = context["contracts"]
        to_approve = context["contract_to_approve"]
        to_sign = context["contract_to_sign"]

        self.assertEqual(len(contracts), 0)
        self.assertEqual(latest, to_sign)
        self.assertIsNone(to_approve)

    def test_all_signed_and_unapproved_returns_latest(self):
        project = ProjectFactory()
        ContractFactory(project=project, signed_by_applicant=True, approver=None)
        ContractFactory(project=project, signed_by_applicant=True, approver=None)
        latest = ContractFactory(
            project=project, signed_by_applicant=True, approver=None
        )

        context = self.DummyContractsView(project).get_context_data()

        contracts = context["contracts"]
        to_approve = context["contract_to_approve"]
        to_sign = context["contract_to_sign"]

        self.assertEqual(len(contracts), 0)
        self.assertEqual(latest, to_approve)
        self.assertIsNone(to_sign)

    def test_mixture_of_both_latest_unsigned_and_unapproved(self):
        project = ProjectFactory()
        user = StaffFactory()
        ContractFactory(project=project, signed_by_applicant=True, approver=None)
        ContractFactory(project=project, signed_by_applicant=True, approver=user)
        ContractFactory(project=project, signed_by_applicant=False, approver=None)
        ContractFactory(project=project, signed_by_applicant=True, approver=user)
        latest = ContractFactory(
            project=project, signed_by_applicant=False, approver=None
        )

        context = self.DummyContractsView(project).get_context_data()

        contracts = context["contracts"]
        to_approve = context["contract_to_approve"]
        to_sign = context["contract_to_sign"]

        self.assertEqual(len(contracts), 2)
        self.assertEqual(latest, to_sign)
        self.assertIsNone(to_approve)

    def test_mixture_of_both_latest_signed_and_unapproved(self):
        project = ProjectFactory()
        user = StaffFactory()
        ContractFactory(project=project, signed_by_applicant=True, approver=None)
        ContractFactory(project=project, signed_by_applicant=True, approver=user)
        ContractFactory(project=project, signed_by_applicant=False, approver=None)
        ContractFactory(project=project, signed_by_applicant=True, approver=user)
        latest = ContractFactory(
            project=project, signed_by_applicant=True, approver=None
        )

        context = self.DummyContractsView(project).get_context_data()

        contracts = context["contracts"]
        to_approve = context["contract_to_approve"]
        to_sign = context["contract_to_sign"]

        self.assertEqual(len(contracts), 2)
        self.assertEqual(latest, to_approve)
        self.assertIsNone(to_sign)

    def test_mixture_of_both_latest_signed_and_approved(self):
        project = ProjectFactory()
        user = StaffFactory()
        ContractFactory(project=project, signed_by_applicant=True, approver=None)
        ContractFactory(project=project, signed_by_applicant=True, approver=user)
        ContractFactory(project=project, signed_by_applicant=False, approver=None)
        ContractFactory(project=project, signed_by_applicant=True, approver=user)
        ContractFactory(project=project, signed_by_applicant=True, approver=user)

        context = self.DummyContractsView(project).get_context_data()

        contracts = context["contracts"]
        to_approve = context["contract_to_approve"]
        to_sign = context["contract_to_sign"]

        self.assertEqual(len(contracts), 3)
        self.assertIsNone(to_approve)
        self.assertIsNone(to_sign)


class TestApproveContractView(BaseViewTestCase):
    base_view_name = "detail"
    url_name = "funds:projects:{}"
    user_factory = StaffFactory

    def get_kwargs(self, instance):
        return {"pk": instance.submission.id}

    def test_approve_unapproved_contract(self):
        project = ProjectFactory(status=CONTRACTING)
        contract = ContractFactory(
            project=project, signed_by_applicant=True, approver=None
        )

        response = self.post_page(
            project,
            {
                "id": contract.id,
            },
            view_name="contract_approve",
        )
        self.assertEqual(response.status_code, 200)

        contract.refresh_from_db()
        self.assertEqual(contract.approver, self.user)

        project.refresh_from_db()
        self.assertEqual(project.status, INVOICING_AND_REPORTING)

    def test_approve_already_approved_contract(self):
        project = ProjectFactory(status=INVOICING_AND_REPORTING)
        user = StaffFactory()
        contract = ContractFactory(
            project=project, signed_by_applicant=True, approver=user
        )

        response = self.post_page(
            project,
            {
                "form-submitted-approve_contract_form": "",
                "id": contract.id,
            },
        )
        self.assertEqual(response.status_code, 200)

        contract.refresh_from_db()
        self.assertEqual(contract.approver, user)

        project.refresh_from_db()
        self.assertEqual(project.status, INVOICING_AND_REPORTING)

    def test_approve_unsigned_contract(self):
        project = ProjectFactory()
        contract = ContractFactory(
            project=project, signed_by_applicant=False, approver=None
        )

        response = self.post_page(
            project,
            {
                "id": contract.id,
            },
            view_name="contract_approve",
        )
        self.assertEqual(response.status_code, 200)

    def test_attempt_to_approve_non_latest(self):
        project = ProjectFactory()
        contract_attempt = ContractFactory(
            project=project, signed_by_applicant=True, approver=None
        )
        contract_meant = ContractFactory(
            project=project, signed_by_applicant=True, approver=None
        )

        response = self.post_page(
            project,
            {
                "id": contract_attempt.id,
            },
            view_name="contract_approve",
        )
        self.assertEqual(response.status_code, 200)

        contract_attempt.refresh_from_db()
        contract_meant.refresh_from_db()
        self.assertIsNone(contract_attempt.approver)
        self.assertIsNone(contract_meant.approver)


class BasePacketFileViewTestCase(BaseViewTestCase):
    url_name = "funds:projects:{}"
    base_view_name = "document"

    def get_kwargs(self, instance):
        return {
            "pk": instance.project.submission.pk,
            "file_pk": instance.id,
        }


class TestStaffPacketView(BasePacketFileViewTestCase):
    user_factory = StaffFactory

    def test_staff_can_access(self):
        document = PacketFileFactory()
        response = self.get_page(document)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [])


class TestUserPacketView(BasePacketFileViewTestCase):
    user_factory = ApplicantFactory

    def test_owner_can_access(self):
        document = PacketFileFactory(project__user=self.user)
        response = self.get_page(document)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain, [])

    def test_user_can_not_access(self):
        document = PacketFileFactory()
        response = self.get_page(document)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.redirect_chain, [])


class TestAnonPacketView(BasePacketFileViewTestCase):
    user_factory = AnonymousUser

    def test_anonymous_can_not_access(self):
        document = PacketFileFactory()
        response = self.get_page(document)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.redirect_chain), 1)
        for path, _ in response.redirect_chain:
            self.assertIn(reverse(settings.LOGIN_URL), path)


class TestProjectDetailApprovalView(TestCase):
    def test_staff_only(self):
        factory = RequestFactory()
        project = ProjectFactory()

        request = factory.get(f"/project/{project.pk}")
        request.user = StaffFactory()

        response = ProjectDetailApprovalView.as_view()(
            request, pk=project.submission.id
        )
        self.assertEqual(response.status_code, 200)

        request.user = ApplicantFactory()
        with self.assertRaises(PermissionDenied):
            ProjectDetailApprovalView.as_view()(request, pk=project.submission.id)


class TestStaffDetailInvoiceStatus(BaseViewTestCase):
    base_view_name = "invoice-detail"
    url_name = "funds:projects:{}"
    user_factory = StaffFactory

    def get_kwargs(self, instance):
        return {
            "pk": instance.project.pk,
            "invoice_pk": instance.pk,
        }

    def test_can(self):
        invoice = InvoiceFactory()
        response = self.get_page(
            invoice, url_kwargs={"pk": invoice.project.submission.pk}
        )
        self.assertEqual(response.status_code, 200)

    def test_wrong_project_cant(self):
        other_project = ProjectFactory()
        invoice = InvoiceFactory()
        response = self.get_page(invoice, url_kwargs={"pk": other_project.pk})
        self.assertEqual(response.status_code, 404)


class TestFinanceDetailInvoiceStatus(BaseViewTestCase):
    base_view_name = "invoice-detail"
    url_name = "funds:projects:{}"
    user_factory = FinanceFactory

    def get_kwargs(self, instance):
        return {
            "pk": instance.project.submission.pk,
            "invoice_pk": instance.pk,
        }

    def test_can(self):
        invoice = InvoiceFactory()
        response = self.get_page(
            invoice, url_kwargs={"pk": invoice.project.submission.pk}
        )
        self.assertEqual(response.status_code, 200)

    def test_wrong_project_cant(self):
        other_project = ProjectFactory()
        invoice = InvoiceFactory()
        response = self.get_page(invoice, url_kwargs={"pk": other_project.pk})
        self.assertEqual(response.status_code, 404)


class TestApplicantDetailInvoiceStatus(BaseViewTestCase):
    base_view_name = "invoice-detail"
    url_name = "funds:projects:{}"
    user_factory = ApplicantFactory

    def get_kwargs(self, instance):
        return {
            "pk": instance.project.submission.pk,
            "invoice_pk": instance.pk,
        }

    def test_can(self):
        invoice = InvoiceFactory(project__user=self.user)
        response = self.get_page(invoice)
        self.assertEqual(response.status_code, 200)

    def test_other_cant(self):
        invoice = InvoiceFactory()
        response = self.get_page(invoice)
        self.assertEqual(response.status_code, 403)


class TestApplicantEditInvoiceView(BaseViewTestCase):
    base_view_name = "invoice-edit"
    url_name = "funds:projects:{}"
    user_factory = ApplicantFactory

    def get_kwargs(self, instance):
        return {
            "pk": instance.project.submission.pk,
            "invoice_pk": instance.pk,
        }

    def test_editing_invoice_remove_supporting_document(self):
        invoice = InvoiceFactory(project__user=self.user)
        SupportingDocumentFactory(invoice=invoice)

        self.assertTrue(invoice.supporting_documents.exists())

        response = self.post_page(
            invoice,
            {
                "invoice_number": invoice.invoice_number,
                "invoice_amount": invoice.invoice_amount,
                "invoice_date": invoice.invoice_date,
                "comment": "test comment",
                "invoice": "",
                "supporting_documents-uploads": "[]",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(invoice.supporting_documents.exists())

    def test_editing_payment_keeps_receipts(self):
        project = ProjectFactory(user=self.user)
        invoice = InvoiceFactory(project=project)
        supporting_document = SupportingDocumentFactory(invoice=invoice)

        response = self.post_page(
            invoice,
            {
                "invoice_number": invoice.invoice_number,
                "invoice_amount": invoice.invoice_amount,
                "invoice_date": invoice.invoice_date,
                "comment": "test comment",
                "invoice": "",
                "supporting_documents-uploads": json.dumps(
                    [
                        {
                            "name": supporting_document.document.name,
                            "size": supporting_document.document.size,
                            "type": "existing",
                        }
                    ]
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(project.invoices.count(), 1)

        invoice.refresh_from_db()

        self.assertEqual(project.invoices.first().pk, invoice.pk)
        self.assertEqual(
            invoice.supporting_documents.first().document, supporting_document.document
        )


class TestStaffEditInvoiceView(BaseViewTestCase):
    base_view_name = "invoice-edit"
    url_name = "funds:projects:{}"
    user_factory = StaffFactory

    def get_kwargs(self, instance):
        return {
            "pk": instance.project.submission.pk,
            "invoice_pk": instance.pk,
        }

    def test_editing_invoice_remove_supporting_document(self):
        invoice = InvoiceFactory()
        SupportingDocumentFactory(invoice=invoice)

        response = self.post_page(
            invoice,
            {
                "invoice_number": invoice.invoice_number,
                "invoice_amount": invoice.invoice_amount,
                "invoice_date": invoice.invoice_date,
                "comment": "test comment",
                "invoice": "",
                "supporting_documents-uploads": "[]",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertFalse(invoice.supporting_documents.exists())

    def test_editing_invoice_keeps_supporting_document(self):
        project = ProjectFactory()
        invoice = InvoiceFactory(project=project)
        supporting_document = SupportingDocumentFactory(invoice=invoice)

        document = BytesIO(b"somebinarydata")
        document.name = "test_invoice.pdf"

        response = self.post_page(
            invoice,
            {
                "invoice_number": invoice.invoice_number,
                "invoice_amount": invoice.invoice_amount,
                "comment": "test comment",
                "document": document,
                "supporting_documents-uploads": json.dumps(
                    [
                        {
                            "name": supporting_document.document.name,
                            "size": supporting_document.document.size,
                            "type": "existing",
                        }
                    ]
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(project.invoices.count(), 1)

        invoice.refresh_from_db()

        self.assertEqual(project.invoices.first().pk, invoice.pk)

        self.assertEqual(
            invoice.supporting_documents.first().document, supporting_document.document
        )


class TestStaffChangeInvoiceStatus(BaseViewTestCase):
    base_view_name = "invoice-detail"
    url_name = "funds:projects:{}"
    user_factory = StaffFactory

    def get_kwargs(self, instance):
        return {
            "pk": instance.project.submission.pk,
            "invoice_pk": instance.pk,
        }

    def test_can(self):
        invoice = InvoiceFactory()
        response = self.post_page(
            invoice,
            {
                "status": CHANGES_REQUESTED_BY_STAFF,
                "comment": "this is a comment",
            },
            view_name="invoice-update",
        )
        self.assertEqual(response.status_code, 204)
        self.assertTrue("invoicesUpdated" in response.headers.get("HX-Trigger", ""))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, CHANGES_REQUESTED_BY_STAFF)

    def test_can_view_updated_invoice_table(self):
        project = ProjectFactory()
        invoice = InvoiceFactory(project=project)
        response = self.post_page(
            invoice,
            {
                "status": CHANGES_REQUESTED_BY_STAFF,
                "comment": "this is a comment",
            },
            view_name="invoice-update",
        )
        self.assertEqual(response.status_code, 204)
        self.assertTrue("invoicesUpdated" in response.headers.get("HX-Trigger", ""))
        response = self.client.get(
            reverse(
                "apply:projects:partial-invoices-status", kwargs={"pk": project.pk}
            ),
            secure=True,
            follow=True,
        )
        self.assertContains(
            response, get_invoice_status_display_value(CHANGES_REQUESTED_BY_STAFF)
        )

    def test_can_view_updated_rejected_invoice_table(self):
        project = ProjectFactory()
        invoice = InvoiceFactory(project=project)
        response = self.post_page(
            invoice,
            {
                "status": DECLINED,
                "comment": "this is a comment",
            },
            view_name="invoice-update",
        )
        self.assertEqual(response.status_code, 204)
        self.assertTrue("invoicesUpdated" in response.headers.get("HX-Trigger", ""))
        self.assertTrue(
            "rejectedInvoicesUpdated" in response.headers.get("HX-Trigger", "")
        )
        response = self.client.get(
            reverse(
                "apply:projects:partial-invoices-status", kwargs={"pk": project.pk}
            ),
            secure=True,
            follow=True,
        )
        self.assertNotContains(response, get_invoice_status_display_value(DECLINED))

        rejected_response = self.client.get(
            reverse(
                "apply:projects:partial-rejected-invoices-status",
                kwargs={"pk": project.pk},
            ),
            secure=True,
            follow=True,
        )
        self.assertContains(
            rejected_response, get_invoice_status_display_value(DECLINED)
        )

    def test_can_view_updated_invoice_status(self):
        project = ProjectFactory()
        invoice = InvoiceFactory(project=project)

        response = self.client.get(
            reverse(
                "apply:projects:partial-invoice-status",
                kwargs={"pk": project.submission.pk, "invoice_pk": invoice.pk},
            ),
            secure=True,
            follow=True,
        )
        self.assertNotContains(
            response, get_invoice_status_display_value(CHANGES_REQUESTED_BY_STAFF)
        )

        response = self.post_page(
            invoice,
            {
                "status": CHANGES_REQUESTED_BY_STAFF,
                "comment": "this is a comment",
            },
            view_name="invoice-update",
        )
        self.assertEqual(response.status_code, 204)
        self.assertTrue("invoicesUpdated" in response.headers.get("HX-Trigger", ""))
        response = self.client.get(
            reverse(
                "apply:projects:partial-invoice-status",
                kwargs={"pk": project.pk, "invoice_pk": invoice.pk},
            ),
            secure=True,
            follow=True,
        )
        self.assertContains(
            response, get_invoice_status_display_value(CHANGES_REQUESTED_BY_STAFF)
        )


class TestApplicantChangeInvoiceStatus(BaseViewTestCase):
    base_view_name = "invoice-detail"
    url_name = "funds:projects:{}"
    user_factory = ApplicantFactory

    def get_kwargs(self, instance):
        return {"pk": instance.project.submission.pk, "invoice_pk": instance.pk}

    def test_can(self):
        invoice = InvoiceFactory(project__user=self.user)
        response = self.post_page(
            invoice,
            {
                "form-submitted-change_invoice_status": "",
                "status": CHANGES_REQUESTED_BY_STAFF,
            },
        )
        self.assertEqual(response.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, SUBMITTED)

    def test_other_cant(self):
        invoice = InvoiceFactory()
        response = self.post_page(
            invoice,
            {
                "form-submitted-change_invoice_status": "",
                "status": CHANGES_REQUESTED_BY_STAFF,
            },
        )
        self.assertEqual(response.status_code, 403)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, SUBMITTED)


class TestStaffInvoiceDocumentPrivateMedia(BaseViewTestCase):
    base_view_name = "invoice-document"
    url_name = "funds:projects:{}"
    user_factory = StaffFactory

    def get_kwargs(self, instance):
        return {"pk": instance.project.submission.pk, "invoice_pk": instance.pk}

    def test_can_access(self):
        invoice = InvoiceFactory()
        response = self.get_page(
            invoice, url_kwargs={"pk": invoice.project.submission.pk}
        )
        self.assertContains(response, invoice.document.read())

    def test_cant_access_if_project_wrong(self):
        other_project = ProjectFactory()
        invoice = InvoiceFactory()
        response = self.get_page(invoice, url_kwargs={"pk": other_project.pk})
        self.assertEqual(response.status_code, 404)


class TestApplicantInvoiceDocumentPrivateMedia(BaseViewTestCase):
    base_view_name = "invoice-document"
    url_name = "funds:projects:{}"
    user_factory = ApplicantFactory

    def get_kwargs(self, instance):
        return {"pk": instance.project.submission.pk, "invoice_pk": instance.pk}

    def test_can_access_own(self):
        invoice = InvoiceFactory(project__user=self.user)
        response = self.get_page(invoice)
        self.assertContains(response, invoice.document.read())

    def test_cant_access_other(self):
        invoice = InvoiceFactory()
        response = self.get_page(invoice)
        self.assertEqual(response.status_code, 403)


class TestStaffInvoiceSupportingDocumentPrivateMedia(BaseViewTestCase):
    base_view_name = "invoice-supporting-document"
    url_name = "funds:projects:{}"
    user_factory = StaffFactory

    def get_kwargs(self, instance):
        return {
            "pk": instance.invoice.project.submission.pk,
            "invoice_pk": instance.invoice.pk,
            "file_pk": instance.pk,
        }

    def test_can_access(self):
        supporting_document = SupportingDocumentFactory()
        response = self.get_page(supporting_document)
        self.assertContains(response, supporting_document.document.read())


class TestApplicantSupportingDocumentPrivateMedia(BaseViewTestCase):
    base_view_name = "invoice-supporting-document"
    url_name = "funds:projects:{}"
    user_factory = ApplicantFactory

    def get_kwargs(self, instance):
        return {
            "pk": instance.invoice.project.submission.pk,
            "invoice_pk": instance.invoice.pk,
            "file_pk": instance.pk,
        }

    def test_can_access_own(self):
        supporting_document = SupportingDocumentFactory(
            invoice__project__user=self.user
        )
        response = self.get_page(supporting_document)
        self.assertContains(response, supporting_document.document.read())

    def test_cant_access_other(self):
        supporting_document = SupportingDocumentFactory()
        response = self.get_page(supporting_document)
        self.assertEqual(response.status_code, 403)


class TestProjectListView(TestCase):
    def test_staff_can_access_project_list_page(self):
        ProjectFactory(status=CONTRACTING)
        ProjectFactory(status=INVOICING_AND_REPORTING)

        self.client.force_login(StaffFactory())

        url = reverse("apply:projects:all")

        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 200)

    def test_applicants_cannot_access_project_list_page(self):
        ProjectFactory(status=CONTRACTING)
        ProjectFactory(status=INVOICING_AND_REPORTING)

        self.client.force_login(UserFactory())

        url = reverse("apply:projects:all")

        response = self.client.get(url, follow=True)
        self.assertEqual(response.status_code, 403)


class TestStaffProjectDetailDownloadView(BaseViewTestCase):
    base_view_name = "download"
    url_name = "funds:projects:{}"
    user_factory = StaffFactory

    def get_kwargs(self, instance):
        return {
            "pk": instance.submission.pk,
        }

    def test_can_access_pdf(self):
        project = ProjectFactory()
        response = self.get_page(project, url_kwargs={"export_type": "pdf"})
        self.assertEqual(response.status_code, 200)

    def test_can_access_docx(self):
        project = ProjectFactory()
        response = self.get_page(project, url_kwargs={"export_type": "docx"})
        self.assertEqual(response.status_code, 200)

    def test_response_object_is_pdf(self):
        project = ProjectFactory()
        response = self.get_page(project, url_kwargs={"export_type": "pdf"})
        self.assertIn(
            ".pdf", response.headers["content-disposition"].split("filename=")[1]
        )

    def test_response_object_is_docx(self):
        project = ProjectFactory()
        response = self.get_page(project, url_kwargs={"export_type": "docx"})
        self.assertIn(
            ".docx", response.headers["content-disposition"].split("filename=")[1]
        )


class ApplicantStaffProjectDetailDownloadView(BaseViewTestCase):
    base_view_name = "download"
    url_name = "funds:projects:{}"
    user_factory = ApplicantFactory

    def get_kwargs(self, instance):
        return {
            "pk": instance.pk,
        }

    def test_cant_access_pdf(self):
        project = ProjectFactory()
        response = self.get_page(project, url_kwargs={"export_type": "pdf"})
        self.assertEqual(response.status_code, 403)

    def test_cant_access_docx(self):
        project = ProjectFactory()
        response = self.get_page(project, url_kwargs={"export_type": "docx"})
        self.assertEqual(response.status_code, 403)
