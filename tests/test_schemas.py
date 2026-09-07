import pytest
from pydantic import ValidationError
from src.schemas import ComplaintExtraction

def test_valid_complaint_schema():
    data = {
        "customer_name": "Anita Rao",
        "email": "anita@example.com",
        "phone_number": "9876543210",
        "complaint_category": "Billing",
        "issue_description": "Charged twice for subscription",
        "resolution_provided": "Refund initiated",
        "is_complaint": True,
        "escalation_required": False,
        "supporting_document_available": True,
        "case_status": "In Progress"
    }
    obj = ComplaintExtraction(**data)
    assert obj.customer_name == "Anita Rao"
    assert obj.case_status == "In Progress"
    assert obj.is_complaint is True

def test_invalid_status_enum():
    data = {
        "customer_name": "Anita Rao",
        "complaint_category": "Billing",
        "issue_description": "Charged twice",
        "is_complaint": True,
        "escalation_required": False,
        "supporting_document_available": False,
        "case_status": "Under Investigation"  # Invalid literal status
    }
    with pytest.raises(ValidationError):
        ComplaintExtraction(**data)

def test_missing_required_field():
    data = {
        "customer_name": "Anita Rao",
        # Missing complaint_category and issue_description
        "is_complaint": True,
        "escalation_required": False,
        "supporting_document_available": False
    }
    with pytest.raises(ValidationError):
        ComplaintExtraction(**data)