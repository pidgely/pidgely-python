"""Typed request parameters and responses.

Parameters use the API's snake_case keys, exactly as in the REST API and the Resend
Python SDK. Responses are plain ``dict`` objects typed with ``TypedDict``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict, Union

__all__ = [
    "RequestOptions",
    "BatchRequestOptions",
    "Tag",
    "Attachment",
    "TemplateRef",
    "SendEmailParams",
    "UpdateEmailParams",
    "ListParams",
    "ListAttachmentsParams",
    "GetAttachmentParams",
    "CreateDomainParams",
    "UpdateDomainParams",
    "CreateApiKeyParams",
    "UpdateApiKeyParams",
    "CreateContactParams",
    "ContactInput",
    "BatchContactsParams",
    "ContactSelector",
    "UpdateContactParams",
    "ListContactsParams",
    "ContactSegmentsParams",
    "ContactSegmentParams",
    "CreateSegmentParams",
    "UpdateSegmentParams",
    "CreateBroadcastParams",
    "UpdateBroadcastParams",
    "SendBroadcastParams",
    "TemplateVariableParams",
    "CreateTemplateParams",
    "UpdateTemplateParams",
    "PreviewTemplateParams",
    "CreateWebhookParams",
    "UpdateWebhookParams",
    "AddSuppressionParams",
    "ListSuppressionsParams",
    "BatchAddSuppressionsParams",
    "BatchRemoveSuppressionsParams",
    "Id",
    "ObjectId",
    "Deleted",
    "Email",
    "EmailList",
    "EmailAttachment",
    "EmailAttachmentList",
    "BatchError",
    "BatchResponse",
    "DomainRecord",
    "Domain",
    "DomainList",
    "ApiKey",
    "ApiKeyList",
    "CreatedApiKey",
    "ContactProperty",
    "Contact",
    "ContactList",
    "ContactDeleted",
    "ContactBatchItem",
    "ContactBatchResult",
    "Segment",
    "SegmentList",
    "CreatedSegment",
    "ContactSegmentRemoved",
    "Broadcast",
    "BroadcastList",
    "TemplateVariable",
    "Template",
    "TemplateList",
    "TemplatePreview",
    "Webhook",
    "WebhookList",
    "WebhookSecret",
    "Suppression",
    "SuppressionList",
    "SuppressionsAdded",
    "SuppressionsRemoved",
    "WebhookEvent",
]

StrOrList = Union[str, List[str]]

# --------------------------------------------------------------------------- options


class RequestOptions(TypedDict, total=False):
    """Per-request options accepted by every method."""

    idempotency_key: str
    """Sent as ``Idempotency-Key``: the API replays the stored response for 24 hours and
    answers 409 when the body differs. Also makes a POST safe to retry automatically."""
    headers: Dict[str, str]
    """Extra headers for this request."""
    timeout: float
    """Per-attempt timeout in seconds (overrides the client option)."""
    max_retries: int
    """Maximum retries for this request (overrides the client option)."""


class BatchRequestOptions(RequestOptions, total=False):
    batch_validation: Literal["strict", "permissive"]
    """``strict`` (default): all or nothing. ``permissive``: valid emails are sent and
    invalid ones reported in ``errors``."""


# --------------------------------------------------------------------------- emails


class Tag(TypedDict):
    name: str
    value: str


class Attachment(TypedDict, total=False):
    filename: str
    content: Union[str, bytes, List[int]]
    """Base64 string, raw ``bytes`` or a list of byte values. Use ``content`` or ``path``."""
    path: str
    """http(s) URL downloaded at send time."""
    content_type: str
    content_id: str
    """Makes the attachment inline; reference it as ``cid:<content_id>``."""


class _TemplateRefRequired(TypedDict):
    id: str


class TemplateRef(_TemplateRefRequired, total=False):
    variables: Dict[str, Union[str, int, float]]


class _SendEmailRequired(TypedDict):
    to: StrOrList


_SendEmailBase = TypedDict(
    "_SendEmailBase",
    {
        "from": str,
        "cc": StrOrList,
        "bcc": StrOrList,
        "reply_to": StrOrList,
        "subject": str,
        "html": str,
        "text": str,
        "headers": Dict[str, str],
        "attachments": List[Attachment],
        "tags": List[Tag],
        "scheduled_at": str,
        "template": TemplateRef,
        "topic_id": str,
        "stream": Literal["transactional", "broadcast"],
    },
    total=False,
)


class SendEmailParams(_SendEmailRequired, _SendEmailBase, total=False):
    """Body of ``POST /emails``. ``from`` may come from the template; ``text`` is
    generated from ``html`` when omitted; ``scheduled_at`` takes ISO 8601 or natural
    language (``"in 1 hour"``), within 30 days."""


class UpdateEmailParams(TypedDict):
    id: str
    scheduled_at: str


class ListParams(TypedDict, total=False):
    """Cursor pagination: ``after`` / ``before`` take an item id."""

    limit: int
    after: str
    before: str


class _EmailIdRequired(TypedDict):
    email_id: str


class ListAttachmentsParams(_EmailIdRequired, ListParams, total=False):
    pass


class GetAttachmentParams(TypedDict):
    email_id: str
    id: str


# --------------------------------------------------------------------------- domains


class _NameRequired(TypedDict):
    name: str


class DomainCapabilities(TypedDict, total=False):
    sending: str
    receiving: str


class CreateDomainParams(_NameRequired, total=False):
    region: str
    custom_return_path: str
    """Bounce subdomain label (default ``bounces``)."""
    tls: Literal["opportunistic", "enforced"]
    open_tracking: bool
    click_tracking: bool
    capabilities: DomainCapabilities


class _IdRequired(TypedDict):
    id: str


class UpdateDomainParams(_IdRequired, total=False):
    tls: Literal["opportunistic", "enforced"]
    open_tracking: bool
    click_tracking: bool


# --------------------------------------------------------------------------- api keys


class CreateApiKeyParams(_NameRequired, total=False):
    permission: Literal["full_access", "sending_access"]
    domain_id: str
    """Restrict a ``sending_access`` key to one domain."""


class UpdateApiKeyParams(TypedDict):
    name: str


# --------------------------------------------------------------------------- contacts

PropertyValue = Union[str, int, float, bool, None]


class _SegmentRef(TypedDict):
    id: str


class _EmailRequired(TypedDict):
    email: str


class CreateContactParams(_EmailRequired, total=False):
    first_name: str
    last_name: str
    unsubscribed: bool
    properties: Dict[str, PropertyValue]
    segments: List[_SegmentRef]
    audience_id: str
    """Deprecated: creates the contact through the legacy ``/audiences/{id}/contacts`` route."""


class ContactInput(_EmailRequired, total=False):
    """One row of :class:`BatchContactsParams`: created, or updated when the email exists."""

    first_name: str
    last_name: str
    unsubscribed: bool
    properties: Dict[str, PropertyValue]
    segments: List[_SegmentRef]


class _ContactsRequired(TypedDict):
    contacts: List[ContactInput]
    """Up to 1,000 contacts, each saved independently."""


class BatchContactsParams(_ContactsRequired, total=False):
    segment_id: str
    """Segment every row is added to."""


class ContactSelector(TypedDict, total=False):
    """Select a contact by ``id`` or by ``email``."""

    id: str
    email: str
    audience_id: str
    """Deprecated: legacy audience route."""


class UpdateContactParams(ContactSelector, total=False):
    first_name: Union[str, None]
    last_name: Union[str, None]
    unsubscribed: bool
    """Kept in sync with the suppression list."""
    properties: Dict[str, PropertyValue]


class ListContactsParams(ListParams, total=False):
    segment_id: str
    audience_id: str
    """Deprecated: use ``segment_id``."""


class ContactSegmentsParams(ListParams, total=False):
    """Select the contact by ``email``, ``id`` or ``contact_id``."""

    email: str
    id: str
    contact_id: str


class _SegmentIdRequired(TypedDict):
    segment_id: str


class ContactSegmentParams(_SegmentIdRequired, total=False):
    email: str
    id: str
    contact_id: str


class CreateSegmentParams(TypedDict):
    name: str


class UpdateSegmentParams(TypedDict):
    name: str


# --------------------------------------------------------------------------- broadcasts

_BroadcastFields = TypedDict(
    "_BroadcastFields",
    {
        "segment_id": str,
        "audience_id": str,
        "from": str,
        "subject": str,
        "reply_to": StrOrList,
        "html": str,
        "text": str,
        "name": str,
        "preview_text": str,
        "scheduled_at": str,
        "topic_id": str,
    },
    total=False,
)


class CreateBroadcastParams(_BroadcastFields, total=False):
    """Body of ``POST /broadcasts``. ``html`` supports ``{{{FIRST_NAME|there}}}``,
    ``{{{contact.<property>}}}`` and ``{{{PIDGELY_UNSUBSCRIBE_URL}}}``."""

    send: bool
    """Send right away (or at ``scheduled_at``) instead of creating a draft."""


class UpdateBroadcastParams(_BroadcastFields, total=False):
    pass


class SendBroadcastParams(TypedDict, total=False):
    scheduled_at: str
    """ISO 8601 or natural language. Omit to send now."""


# --------------------------------------------------------------------------- templates


class _VariableRequired(TypedDict):
    key: str
    type: Literal["string", "number"]


class TemplateVariableParams(_VariableRequired, total=False):
    fallback_value: Union[str, int, float, None]


_TemplateFields = TypedDict(
    "_TemplateFields",
    {
        "alias": str,
        "from": str,
        "subject": str,
        "reply_to": StrOrList,
        "html": str,
        "text": str,
        "variables": List[TemplateVariableParams],
    },
    total=False,
)


class CreateTemplateParams(_NameRequired, _TemplateFields, total=False):
    pass


class UpdateTemplateParams(_TemplateFields, total=False):
    name: str


class PreviewTemplateParams(TypedDict, total=False):
    variables: Dict[str, Union[str, int, float]]
    """Values to render with; variables that are not given use their fallback value."""


# --------------------------------------------------------------------------- webhooks


class CreateWebhookParams(TypedDict):
    endpoint: str
    events: List[str]


class UpdateWebhookParams(TypedDict, total=False):
    endpoint: str
    events: List[str]
    status: Literal["enabled", "disabled"]


# --------------------------------------------------------------------------- suppressions

SuppressionOrigin = Literal["bounce", "complaint", "manual", "unsubscribe"]


class AddSuppressionParams(TypedDict):
    email: str


class ListSuppressionsParams(ListParams, total=False):
    origin: SuppressionOrigin


class BatchAddSuppressionsParams(TypedDict):
    emails: List[str]


class BatchRemoveSuppressionsParams(TypedDict, total=False):
    emails: List[str]
    ids: List[str]


# --------------------------------------------------------------------------- responses


class Id(TypedDict):
    id: str


class ObjectId(TypedDict):
    object: str
    id: str


class Deleted(TypedDict):
    object: str
    id: str
    deleted: bool


_EmailFields = TypedDict(
    "_EmailFields",
    {
        "object": str,
        "id": str,
        "message_id": str,
        "to": List[str],
        "cc": List[str],
        "bcc": List[str],
        "reply_to": List[str],
        "from": str,
        "subject": str,
        "html": Union[str, None],
        "text": Union[str, None],
        "created_at": str,
        "scheduled_at": Union[str, None],
        "last_event": str,
        "tags": List[Tag],
    },
    total=False,
)


class Email(_EmailFields, total=False):
    """A sent email. ``last_event`` is queued, scheduled, sent, delivered,
    delivery_delayed, bounced, complained, suppressed, failed or canceled."""


class _ListFields(TypedDict):
    object: str
    has_more: bool


class EmailList(_ListFields):
    data: List[Email]


class EmailAttachment(TypedDict, total=False):
    object: str
    id: str
    filename: str
    size: int
    content_type: str
    content_disposition: Literal["attachment", "inline"]
    content_id: Union[str, None]
    download_url: str
    """Signed link, valid for 1 hour."""
    expires_at: str


class EmailAttachmentList(_ListFields):
    data: List[EmailAttachment]


class BatchError(TypedDict):
    index: int
    message: str


class _BatchData(TypedDict):
    data: List[Id]


class BatchResponse(_BatchData, total=False):
    errors: List[BatchError]


class DomainRecord(TypedDict, total=False):
    record: Literal["DKIM", "SPF", "DMARC"]
    name: str
    type: Literal["TXT", "MX"]
    ttl: str
    status: str
    value: str
    priority: int


class Domain(TypedDict, total=False):
    object: str
    id: str
    name: str
    status: Literal["not_started", "pending", "verified", "failed"]
    created_at: str
    region: str
    open_tracking: bool
    click_tracking: bool
    tls: Literal["opportunistic", "enforced"]
    capabilities: DomainCapabilities
    records: List[DomainRecord]
    """DNS records to publish. Present on create/get, omitted in lists."""


class DomainList(_ListFields):
    data: List[Domain]


class ApiKey(TypedDict, total=False):
    id: str
    name: str
    permission: Literal["full_access", "sending_access"]
    created_at: str
    last_used_at: Union[str, None]


class ApiKeyList(_ListFields):
    data: List[ApiKey]


class CreatedApiKey(TypedDict):
    object: str
    id: str
    token: str
    """The secret ``pdg_…`` key, shown only once."""


class ContactProperty(TypedDict):
    value: Any
    type: Literal["string", "number", "boolean"]


class Contact(TypedDict, total=False):
    object: str
    id: str
    email: str
    first_name: str
    last_name: str
    created_at: str
    unsubscribed: bool
    properties: Dict[str, ContactProperty]


class ContactList(_ListFields):
    data: List[Contact]


class ContactDeleted(TypedDict, total=False):
    object: str
    contact: str
    id: str
    deleted: bool


class Segment(TypedDict, total=False):
    object: str
    id: str
    name: str
    created_at: str


class SegmentList(_ListFields):
    data: List[Segment]


class CreatedSegment(TypedDict):
    object: str
    id: str
    name: str


class ContactBatchItem(TypedDict):
    index: int
    id: str


class ContactBatchResult(TypedDict):
    """Saved rows in ``data`` and invalid rows in ``errors``, both with their ``index``."""

    object: str
    data: List[ContactBatchItem]
    errors: List[BatchError]


class ContactSegmentRemoved(TypedDict, total=False):
    object: str
    id: str
    segment_id: str
    deleted: bool


_BroadcastResponseFields = TypedDict(
    "_BroadcastResponseFields",
    {
        "object": str,
        "id": str,
        "name": str,
        "segment_id": Union[str, None],
        "audience_id": Union[str, None],
        "from": str,
        "subject": str,
        "reply_to": List[str],
        "preview_text": str,
        "html": str,
        "text": str,
        "status": Literal["draft", "scheduled", "queued", "sending", "sent", "canceled", "failed"],
        "created_at": str,
        "scheduled_at": Union[str, None],
        "sent_at": Union[str, None],
        "topic_id": None,
        "recipients": int,
        "stats": Dict[str, int],
    },
    total=False,
)


class Broadcast(_BroadcastResponseFields, total=False):
    """A broadcast. ``stats`` counts deliveries by status (Pidgely extension)."""


class BroadcastList(_ListFields):
    data: List[Broadcast]


class TemplateVariable(TypedDict, total=False):
    id: str
    key: str
    type: Literal["string", "number"]
    fallback_value: Union[str, int, float, None]
    created_at: str
    updated_at: str


_TemplateResponseFields = TypedDict(
    "_TemplateResponseFields",
    {
        "object": str,
        "id": str,
        "current_version_id": Union[str, None],
        "alias": Union[str, None],
        "name": str,
        "created_at": str,
        "updated_at": str,
        "status": Literal["draft", "published"],
        "published_at": Union[str, None],
        "from": str,
        "subject": str,
        "reply_to": List[str],
        "html": str,
        "text": str,
        "variables": List[TemplateVariable],
        "has_unpublished_versions": bool,
    },
    total=False,
)


class Template(_TemplateResponseFields, total=False):
    pass


class TemplateList(_ListFields):
    data: List[Template]


TemplatePreview = TypedDict(
    "TemplatePreview",
    {
        "object": str,
        "from": str,
        "subject": str,
        "reply_to": List[str],
        "html": str,
        "text": str,
        "missing_variables": List[str],
    },
    total=False,
)
"""A template draft rendered with variables. ``missing_variables`` lists the variables
with neither a value nor a fallback value."""


class Webhook(TypedDict, total=False):
    object: str
    id: str
    created_at: str
    status: Literal["enabled", "disabled"]
    endpoint: str
    events: List[str]
    signing_secret: str


class WebhookList(_ListFields):
    data: List[Webhook]


class WebhookSecret(TypedDict):
    object: str
    id: str
    signing_secret: str
    """``whsec_…``: store it to verify deliveries."""


class Suppression(TypedDict, total=False):
    object: str
    id: str
    email: str
    origin: SuppressionOrigin
    source_id: Union[str, None]
    created_at: str


class SuppressionList(_ListFields):
    data: List[Suppression]


class SuppressionsAdded(TypedDict):
    data: List[ObjectId]


class SuppressionsRemoved(TypedDict):
    data: List[Deleted]


class WebhookEvent(TypedDict):
    """Payload delivered to webhook endpoints (Resend format)."""

    type: str
    created_at: str
    data: Dict[str, Any]
