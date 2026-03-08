import json
from types import SimpleNamespace
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from config.middleware import TenantAwareMainMiddleware, _origin_allowed, _set_cors_headers


class DummyDomainModel:
    class DoesNotExist(Exception):
        pass


@override_settings(
    CORS_ALLOWED_ORIGINS=["http://demo.localhost:5173"],
    CORS_ALLOWED_ORIGIN_REGEXES=[r"^http://[a-z0-9-]+\.localhost:5173$"],
)
class TenantAwareMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantAwareMainMiddleware(lambda request: HttpResponse("ok"))

    def test_origin_allowed_supports_exact_and_regex_matches(self):
        self.assertTrue(_origin_allowed("http://demo.localhost:5173"))
        self.assertTrue(_origin_allowed("http://new-tenant.localhost:5173"))
        self.assertFalse(_origin_allowed("http://new-tenant.localhost:3000"))

    def test_set_cors_headers_applies_allow_origin_and_credentials(self):
        request = self.factory.get("/api/meta/", HTTP_ORIGIN="http://demo.localhost:5173")
        response = _set_cors_headers(HttpResponse("ok"), request)

        self.assertEqual(response["Access-Control-Allow-Origin"], "http://demo.localhost:5173")
        self.assertEqual(response["Access-Control-Allow-Credentials"], "true")
        self.assertEqual(response["Vary"], "Origin")

    def test_options_request_gets_allow_methods_and_headers(self):
        request = self.factory.options(
            "/api/meta/",
            HTTP_ORIGIN="http://demo.localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="X-CSRFToken, Content-Type",
        )
        response = _set_cors_headers(HttpResponse("ok"), request)

        self.assertEqual(response["Access-Control-Allow-Methods"], "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.assertEqual(response["Access-Control-Allow-Headers"], "X-CSRFToken, Content-Type")

    @patch("config.middleware.connection")
    @patch.object(TenantAwareMainMiddleware, "setup_url_routing")
    @patch.object(TenantAwareMainMiddleware, "get_tenant")
    @patch("config.middleware.get_tenant_domain_model")
    def test_public_localhost_without_tenant_falls_back_to_public_routing(
        self,
        get_domain_model,
        get_tenant,
        setup_url_routing,
        connection,
    ):
        get_domain_model.return_value = DummyDomainModel
        get_tenant.side_effect = DummyDomainModel.DoesNotExist

        request = self.factory.get("/api/meta/", HTTP_HOST="localhost:8000")

        response = self.middleware.process_request(request)

        self.assertIsNone(response)
        self.assertEqual(connection.set_schema_to_public.call_count, 2)
        setup_url_routing.assert_called_once_with(request, force_public=True)

    @patch("config.middleware.connection")
    @patch.object(TenantAwareMainMiddleware, "setup_url_routing")
    @patch.object(TenantAwareMainMiddleware, "get_tenant")
    @patch("config.middleware.get_tenant_domain_model")
    def test_unknown_tenant_host_returns_json_404_with_cors(
        self,
        get_domain_model,
        get_tenant,
        setup_url_routing,
        connection,
    ):
        get_domain_model.return_value = DummyDomainModel
        get_tenant.side_effect = DummyDomainModel.DoesNotExist

        request = self.factory.get(
            "/api/meta/",
            HTTP_HOST="ghost.localhost:8000",
            HTTP_ORIGIN="http://ghost.localhost:5173",
        )

        response = self.middleware.process_request(request)

        self.assertEqual(response.status_code, 404)
        payload = json.loads(response.content)
        self.assertEqual(payload["code"], "tenant_not_found")
        self.assertEqual(payload["host"], "ghost.localhost")
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://ghost.localhost:5173")
        self.assertEqual(response["Access-Control-Allow-Credentials"], "true")
        setup_url_routing.assert_not_called()
        connection.set_schema_to_public.assert_called_once()

    @patch("config.middleware.connection")
    @patch.object(TenantAwareMainMiddleware, "get_tenant")
    @patch("config.middleware.get_tenant_domain_model")
    def test_unknown_tenant_options_request_returns_200_with_preflight_headers(
        self,
        get_domain_model,
        get_tenant,
        connection,
    ):
        get_domain_model.return_value = DummyDomainModel
        get_tenant.side_effect = DummyDomainModel.DoesNotExist

        request = self.factory.options(
            "/api/meta/",
            HTTP_HOST="ghost.localhost:8000",
            HTTP_ORIGIN="http://ghost.localhost:5173",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="X-CSRFToken, Content-Type",
        )

        response = self.middleware.process_request(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload["code"], "tenant_not_found")
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://ghost.localhost:5173")
        self.assertEqual(response["Access-Control-Allow-Methods"], "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.assertEqual(response["Access-Control-Allow-Headers"], "X-CSRFToken, Content-Type")
        connection.set_schema_to_public.assert_called_once()

    @patch("config.middleware.connection")
    @patch.object(TenantAwareMainMiddleware, "setup_url_routing")
    @patch.object(TenantAwareMainMiddleware, "get_tenant")
    @patch("config.middleware.get_tenant_domain_model")
    def test_resolved_tenant_sets_schema_and_request_context(
        self,
        get_domain_model,
        get_tenant,
        setup_url_routing,
        connection,
    ):
        get_domain_model.return_value = DummyDomainModel
        tenant = SimpleNamespace(id=42, slug="demo", domain_url="")
        get_tenant.return_value = tenant

        request = self.factory.get("/api/meta/", HTTP_HOST="demo.localhost:8000")

        response = self.middleware.process_request(request)

        self.assertIsNone(response)
        self.assertIs(request.tenant, tenant)
        self.assertEqual(tenant.domain_url, "demo.localhost")
        connection.set_schema_to_public.assert_called_once()
        connection.set_tenant.assert_called_once_with(tenant)
        setup_url_routing.assert_called_once_with(request)

    @patch("config.middleware.connection")
    @patch.object(TenantAwareMainMiddleware, "setup_url_routing")
    @patch.object(TenantAwareMainMiddleware, "get_tenant")
    @patch("config.middleware.get_tenant_domain_model")
    def test_inactive_tenant_returns_json_423(
        self,
        get_domain_model,
        get_tenant,
        setup_url_routing,
        connection,
    ):
        get_domain_model.return_value = DummyDomainModel
        tenant = SimpleNamespace(id=42, slug="demo", domain_url="", is_active=False, lifecycle_status="suspended")
        get_tenant.return_value = tenant

        request = self.factory.get(
            "/api/meta/",
            HTTP_HOST="demo.localhost:8000",
            HTTP_ORIGIN="http://demo.localhost:5173",
        )

        response = self.middleware.process_request(request)

        self.assertEqual(response.status_code, 423)
        payload = json.loads(response.content)
        self.assertEqual(payload["code"], "tenant_inactive")
        self.assertEqual(payload["host"], "demo.localhost")
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://demo.localhost:5173")
        setup_url_routing.assert_not_called()
        connection.set_schema_to_public.assert_called_once()
