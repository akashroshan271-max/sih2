"""Desk custody: which stage, and which moves, belong to which officer role.

The workflow state machine (:mod:`app.services.workflow`) defines what is
*legal* for a docket. This module defines who is *competent* to do it.

    Scrutiny officer   Scrutiny → EVC | SAC | Rejected
    EVC member         EVC → SAC | SHC
    SAC member         SAC → SHC | Approved | Rejected
    SHC member         SHC → Approved | Rejected
    Regional officer   oversight: reads every stage, runs the SLA sweep and may
                       exercise the competent move for any desk (delegated)

A stage officer can only open dockets sitting at their own desk, so an EVC
member never sees the SAC's working papers and a scrutiny officer cannot act on
a file that has already left scrutiny.
"""

from __future__ import annotations

from app.models import (
    Application,
    ApplicationStatus,
    OfficerRole,
)
from app.services.errors import Forbidden
from app.services.workflow import allowed_transitions

#: The stage each desk owns (``None`` = oversight, not a single stage).
STAGE_BY_ROLE: dict[OfficerRole, ApplicationStatus | None] = {
    OfficerRole.SCRUTINY_OFFICER: ApplicationStatus.SCRUTINY,
    OfficerRole.EVC_MEMBER: ApplicationStatus.EVC,
    OfficerRole.SAC_MEMBER: ApplicationStatus.SAC,
    OfficerRole.SHC_MEMBER: ApplicationStatus.SHC,
    OfficerRole.REGIONAL_OFFICER: None,
}

#: Legal moves each desk is competent to make from its own stage.
CUSTODY: dict[OfficerRole, dict[ApplicationStatus, frozenset[ApplicationStatus]]] = {
    OfficerRole.SCRUTINY_OFFICER: {
        ApplicationStatus.SCRUTINY: frozenset(
            {
                ApplicationStatus.EVC,
                ApplicationStatus.SAC,
                ApplicationStatus.REJECTED,
            }
        )
    },
    OfficerRole.EVC_MEMBER: {
        ApplicationStatus.EVC: frozenset(
            {ApplicationStatus.SAC, ApplicationStatus.SHC}
        )
    },
    OfficerRole.SAC_MEMBER: {
        ApplicationStatus.SAC: frozenset(
            {
                ApplicationStatus.SHC,
                ApplicationStatus.APPROVED,
                ApplicationStatus.REJECTED,
            }
        )
    },
    OfficerRole.SHC_MEMBER: {
        ApplicationStatus.SHC: frozenset(
            {ApplicationStatus.APPROVED, ApplicationStatus.REJECTED}
        )
    },
}


def stage_for_role(role: OfficerRole) -> ApplicationStatus | None:
    return STAGE_BY_ROLE.get(role)


def can_act_on(role: OfficerRole, application: Application) -> bool:
    """May this desk open and act on the docket right now?"""
    if role is OfficerRole.REGIONAL_OFFICER:
        return True
    stage = stage_for_role(role)
    return stage is not None and application.status is stage


def ensure_can_view(role: OfficerRole, application: Application) -> None:
    """Read scope: your own stage only, or anything for oversight."""
    if can_act_on(role, application):
        return
    stage = stage_for_role(role)
    raise Forbidden(
        "This docket is not at your desk.",
        context={
            "role": role.value,
            "your_stage": stage.value if stage else "oversight",
            "docket_status": application.status.value,
        },
    )


def permitted_transitions(
    role: OfficerRole, application: Application
) -> tuple[ApplicationStatus, ...]:
    """Legal moves for the docket, narrowed to this desk's competence."""
    legal = allowed_transitions(application)
    if role is OfficerRole.REGIONAL_OFFICER:
        return legal
    competent = CUSTODY.get(role, {}).get(application.status, frozenset())
    return tuple(status for status in legal if status in competent)


def ensure_can_transition(
    role: OfficerRole, application: Application, target: ApplicationStatus
) -> None:
    permitted = permitted_transitions(role, application)
    if target in permitted:
        return
    if target not in allowed_transitions(application):
        # Not a workflow question of custody at all: let the state machine
        # answer with its 409 invalid_transition (or "already decided").
        return
    stage = stage_for_role(role)
    raise Forbidden(
        "This desk cannot make that move.",
        context={
            "role": role.value,
            "your_stage": stage.value if stage else "oversight",
            "docket_status": application.status.value,
            "requested": target.value,
            "permitted": [status.value for status in permitted],
        },
    )


def ensure_can_upload(role: OfficerRole, application: Application) -> None:
    """Evidence may be added only while the docket sits at your desk."""
    if application.status in (ApplicationStatus.APPROVED, ApplicationStatus.REJECTED):
        raise Forbidden(
            "This docket is decided and sealed; documents can no longer be added.",
            context={"docket_status": application.status.value},
        )
    ensure_can_view(role, application)


def ensure_can_create_application(role: OfficerRole) -> None:
    """Intake is registered by the scrutiny cell (or the regional office)."""
    if role in (OfficerRole.SCRUTINY_OFFICER, OfficerRole.REGIONAL_OFFICER):
        return
    raise Forbidden(
        "Only the scrutiny cell or the regional office can register a new docket.",
        context={"role": role.value},
    )
