"""B03 acceptance tests for authentication, RBAC, MFA, and public access."""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.security.auth import create_access_token
from backend.app.security.dependencies import Principal, require_permission
from backend.app.security.rbac import Permission


def _auth_header(
    role: str,
    *,
    mfa: bool = False,
    subject: str = "test@resqshield.local",
) -> dict[str, str]:
    token = create_access_token(
        subject=subject,
        role=role,
        mfa_verified=mfa,
    )
    return {"Authorization": f"Bearer {token}"}


def _rbac_client() -> TestClient:
    app = FastAPI()

    @app.put("/road")
    async def update_road(
        principal: Principal = Depends(
            require_permission(Permission.ROAD_STATUS_UPDATE)
        ),
    ):
        return {"ok": True, "role": principal.role.value}

    @app.put("/shelter")
    async def update_shelter(
        principal: Principal = Depends(
            require_permission(Permission.SHELTER_STATUS_UPDATE)
        ),
    ):
        return {"ok": True, "role": principal.role.value}

    @app.put("/medical")
    async def update_medical(
        principal: Principal = Depends(
            require_permission(Permission.MEDICAL_STATUS_UPDATE)
        ),
    ):
        return {"ok": True, "role": principal.role.value}

    @app.post("/alert/approve")
    async def approve_alert(
        principal: Principal = Depends(
            require_permission(Permission.ALERT_APPROVE)
        ),
    ):
        return {"ok": True, "role": principal.role.value}

    @app.put("/threshold")
    async def update_threshold(
        principal: Principal = Depends(
            require_permission(Permission.THRESHOLD_UPDATE)
        ),
    ):
        return {"ok": True, "role": principal.role.value}

    @app.post("/admin/users")
    async def admin_users(
        principal: Principal = Depends(
            require_permission(Permission.USER_ADMIN)
        ),
    ):
        return {"ok": True, "role": principal.role.value}

    return TestClient(app)


class TestB03PublicAndAuthentication:
    def test_public_alerts_work_without_login(self):
        client = TestClient(create_app())

        response = client.get("/api/v1/public/alerts")

        assert response.status_code == 200
        assert response.json()["access"] == "public"

    def test_protected_me_endpoint_rejects_anonymous_user(self):
        client = TestClient(create_app())

        response = client.get("/api/v1/auth/me")

        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required."

    def test_valid_token_exposes_authenticated_principal(self):
        client = TestClient(create_app())

        response = client.get(
            "/api/v1/auth/me",
            headers=_auth_header("pwd_engineer"),
        )

        assert response.status_code == 200
        assert response.json()["role"] == "pwd_engineer"
        assert response.json()["mfa_verified"] is False


class TestB03LeastPrivilege:
    def test_pwd_can_update_road(self):
        client = _rbac_client()

        response = client.put(
            "/road",
            headers=_auth_header("pwd_engineer"),
        )

        assert response.status_code == 200

    def test_pwd_cannot_admin_users(self):
        client = _rbac_client()

        response = client.post(
            "/admin/users",
            headers=_auth_header("pwd_engineer", mfa=True),
        )

        assert response.status_code == 403

    def test_police_can_update_road(self):
        client = _rbac_client()

        response = client.put(
            "/road",
            headers=_auth_header("police"),
        )

        assert response.status_code == 200

    def test_police_cannot_update_threshold(self):
        client = _rbac_client()

        response = client.put(
            "/threshold",
            headers=_auth_header("police", mfa=True),
        )

        assert response.status_code == 403

    def test_shelter_operator_can_update_shelter(self):
        client = _rbac_client()

        response = client.put(
            "/shelter",
            headers=_auth_header("shelter_operator"),
        )

        assert response.status_code == 200

    def test_shelter_operator_cannot_approve_alert(self):
        client = _rbac_client()

        response = client.post(
            "/alert/approve",
            headers=_auth_header("shelter_operator", mfa=True),
        )

        assert response.status_code == 403

    def test_health_department_can_update_medical_status(self):
        client = _rbac_client()

        response = client.put(
            "/medical",
            headers=_auth_header("health_department"),
        )

        assert response.status_code == 200

    def test_health_department_cannot_admin_users(self):
        client = _rbac_client()

        response = client.post(
            "/admin/users",
            headers=_auth_header("health_department", mfa=True),
        )

        assert response.status_code == 403


class TestB03SensitiveOperations:
    def test_district_officer_cannot_approve_alert_without_mfa(self):
        client = _rbac_client()

        response = client.post(
            "/alert/approve",
            headers=_auth_header("district_officer", mfa=False),
        )

        assert response.status_code == 403
        assert "MFA" in response.json()["detail"]

    def test_district_officer_can_approve_alert_after_mfa(self):
        client = _rbac_client()

        response = client.post(
            "/alert/approve",
            headers=_auth_header("district_officer", mfa=True),
        )

        assert response.status_code == 200

    def test_system_admin_cannot_admin_users_without_mfa(self):
        client = _rbac_client()

        response = client.post(
            "/admin/users",
            headers=_auth_header("system_admin", mfa=False),
        )

        assert response.status_code == 403
        assert "MFA" in response.json()["detail"]

    def test_system_admin_can_admin_users_after_mfa(self):
        client = _rbac_client()

        response = client.post(
            "/admin/users",
            headers=_auth_header("system_admin", mfa=True),
        )

        assert response.status_code == 200
