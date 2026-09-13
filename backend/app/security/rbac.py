"""Role-based access control definitions for ResQShield."""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    """Canonical platform roles defined by the ResQShield specification."""

    CITIZEN = "citizen"
    FIELD_RESPONDER = "field_responder"
    DISTRICT_OFFICER = "district_officer"
    NDRF_CONTROL_ROOM = "ndrf_control_room"
    SDM_COLLECTOR = "sdm_collector"
    PWD_ENGINEER = "pwd_engineer"
    POLICE = "police"
    SHELTER_OPERATOR = "shelter_operator"
    HEALTH_DEPARTMENT = "health_department"
    SYSTEM_ADMIN = "system_admin"
    RESEARCH = "research"


class Permission(StrEnum):
    """Fine-grained permissions used by API authorization checks."""

    PUBLIC_ALERT_READ = "public_alert:read"
    PERSONAL_RISK_READ = "personal_risk:read"
    SOS_CREATE = "sos:create"
    HAZARD_REPORT_CREATE = "hazard_report:create"

    ASSIGNMENT_READ = "assignment:read"
    ASSIGNMENT_ACK = "assignment:ack"
    RESCUE_STATUS_UPDATE = "rescue_status:update"

    ROAD_STATUS_UPDATE = "road_status:update"
    ROAD_CLOSE = "road:close"
    BRIDGE_STATUS_UPDATE = "bridge_status:update"

    SHELTER_STATUS_UPDATE = "shelter_status:update"
    SHELTER_OPEN_CLOSE = "shelter:open_close"

    MEDICAL_STATUS_UPDATE = "medical_status:update"

    ALERT_CREATE = "alert:create"
    ALERT_APPROVE = "alert:approve"

    INCIDENT_READ = "incident:read"
    INCIDENT_MANAGE = "incident:manage"

    THRESHOLD_UPDATE = "threshold:update"
    USER_ADMIN = "user:admin"
    SYSTEM_ADMIN = "system:admin"

    RESEARCH_READ = "research:read"
    RESEARCH_RUN = "research:run"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.CITIZEN: frozenset(
        {
            Permission.PUBLIC_ALERT_READ,
            Permission.PERSONAL_RISK_READ,
            Permission.SOS_CREATE,
            Permission.HAZARD_REPORT_CREATE,
        }
    ),
    Role.FIELD_RESPONDER: frozenset(
        {
            Permission.PUBLIC_ALERT_READ,
            Permission.ASSIGNMENT_READ,
            Permission.ASSIGNMENT_ACK,
            Permission.RESCUE_STATUS_UPDATE,
            Permission.HAZARD_REPORT_CREATE,
            Permission.ROAD_STATUS_UPDATE,
            Permission.BRIDGE_STATUS_UPDATE,
            Permission.SHELTER_STATUS_UPDATE,
            Permission.INCIDENT_READ,
        }
    ),
    Role.PWD_ENGINEER: frozenset(
        {
            Permission.PUBLIC_ALERT_READ,
            Permission.ROAD_STATUS_UPDATE,
            Permission.ROAD_CLOSE,
            Permission.BRIDGE_STATUS_UPDATE,
            Permission.INCIDENT_READ,
        }
    ),
    Role.POLICE: frozenset(
        {
            Permission.PUBLIC_ALERT_READ,
            Permission.ROAD_STATUS_UPDATE,
            Permission.ROAD_CLOSE,
            Permission.INCIDENT_READ,
        }
    ),
    Role.SHELTER_OPERATOR: frozenset(
        {
            Permission.PUBLIC_ALERT_READ,
            Permission.SHELTER_STATUS_UPDATE,
            Permission.INCIDENT_READ,
        }
    ),
    Role.HEALTH_DEPARTMENT: frozenset(
        {
            Permission.PUBLIC_ALERT_READ,
            Permission.MEDICAL_STATUS_UPDATE,
            Permission.INCIDENT_READ,
        }
    ),
    Role.DISTRICT_OFFICER: frozenset(
        {
            Permission.PUBLIC_ALERT_READ,
            Permission.ROAD_STATUS_UPDATE,
            Permission.ROAD_CLOSE,
            Permission.BRIDGE_STATUS_UPDATE,
            Permission.SHELTER_STATUS_UPDATE,
            Permission.SHELTER_OPEN_CLOSE,
            Permission.ALERT_CREATE,
            Permission.ALERT_APPROVE,
            Permission.INCIDENT_READ,
            Permission.INCIDENT_MANAGE,
        }
    ),
    Role.NDRF_CONTROL_ROOM: frozenset(
        {
            Permission.PUBLIC_ALERT_READ,
            Permission.ASSIGNMENT_READ,
            Permission.ALERT_CREATE,
            Permission.ALERT_APPROVE,
            Permission.INCIDENT_READ,
            Permission.INCIDENT_MANAGE,
            Permission.ROAD_STATUS_UPDATE,
            Permission.SHELTER_STATUS_UPDATE,
        }
    ),
    Role.SDM_COLLECTOR: frozenset(
        {
            Permission.PUBLIC_ALERT_READ,
            Permission.ALERT_CREATE,
            Permission.ALERT_APPROVE,
            Permission.INCIDENT_READ,
            Permission.INCIDENT_MANAGE,
            Permission.ROAD_CLOSE,
            Permission.SHELTER_OPEN_CLOSE,
        }
    ),
    Role.RESEARCH: frozenset(
        {
            Permission.PUBLIC_ALERT_READ,
            Permission.RESEARCH_READ,
            Permission.RESEARCH_RUN,
        }
    ),
    Role.SYSTEM_ADMIN: frozenset(Permission),
}


SENSITIVE_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.ALERT_APPROVE,
        Permission.THRESHOLD_UPDATE,
        Permission.USER_ADMIN,
        Permission.SYSTEM_ADMIN,
    }
)


def permissions_for_role(role: Role) -> frozenset[Permission]:
    """Return the explicit permission set assigned to a role."""

    return ROLE_PERMISSIONS[role]


def has_permission(role: Role, permission: Permission) -> bool:
    """Return True when the role explicitly has the requested permission."""

    return permission in permissions_for_role(role)


def requires_mfa(permission: Permission) -> bool:
    """Return whether an operation is sensitive enough to require MFA."""

    return permission in SENSITIVE_PERMISSIONS
