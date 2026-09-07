from pydantic import BaseModel, Field
from typing import Optional, Literal

class ComplaintExtraction(BaseModel):
    """Data contract for structured information extracted from complaint documents."""
    customer_name: str = Field(
        ..., 
        description="Full name of the customer, or 'Valued Customer' if missing."
    )
    email: Optional[str] = Field(
        default=None, 
        description="Customer contact email address, null if not mentioned."
    )
    phone_number: Optional[str] = Field(
        default=None, 
        description="Customer contact phone number, null if not mentioned."
    )
    complaint_category: str = Field(
        ..., 
        description="Core category e.g., Billing, Service Outage, Product Defect, Delivery, Hardware, Support."
    )
    issue_description: str = Field(
        ..., 
        description="Detailed description of the customer's grievance or problem."
    )
    resolution_provided: Optional[str] = Field(
        default=None, 
        description="Action taken, refund issued, or proposed solution; null if unresolved."
    )
    is_complaint: bool = Field(
        ..., 
        description="True if the document describes an active complaint, grievance, or issue; False otherwise."
    )
    escalation_required: bool = Field(
        ..., 
        description="True if urgent managerial attention, legal threat, or severe financial risk is detected."
    )
    supporting_document_available: bool = Field(
        ..., 
        description="True if the text references invoices, receipts, screenshots, or attached files."
    )
    case_status: Literal["Open", "In Progress", "Resolved", "Closed"] = Field(
        default="Open", 
        description="Operational status of the case."
    )