from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve, reverse

from appHome.views import monitoramento


@override_settings(ALLOWED_HOSTS=["localhost"])
class MonitoramentoTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory(HTTP_HOST="localhost").get("/monitoramento/")
        self.request.session = {
            "user_name": "Gestor de teste",
            "user_cargo": "Gestor",
            "fotoPerfil": "perfil.jpg",
        }
        self.request.resolver_match = resolve("/monitoramento/")

    def test_route_requires_login(self):
        self.request.user = AnonymousUser()
        response = monitoramento(self.request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/login/?next=/monitoramento/")
        self.assertEqual(reverse("monitoramento"), "/monitoramento/")

    @override_settings(IOT_STREAM_URL="http://192.168.1.50:5000/video_feed?quality=80")
    def test_view_passes_stream_configuration_and_panel_context(self):
        self.request.user = SimpleNamespace(is_authenticated=True)
        with patch("appHome.views.render", return_value=HttpResponse()) as render:
            response = monitoramento(self.request)
        self.assertIn("no-store", response.headers["Cache-Control"])
        args = render.call_args.args
        self.assertEqual(args[1], "monitoramento.html")
        self.assertEqual(args[2]["stream_url"], "http://192.168.1.50:5000/video_feed?quality=80")
        for key in ("user_name", "user_cargo", "fotoPerfil"):
            self.assertEqual(args[2][key], self.request.session[key])

    def test_stream_attribute_is_escaped_and_sidebar_stays_active(self):
        html = render_to_string("monitoramento.html", {
            "stream_url": 'http://localhost:5000/video_feed?a=1&label="camera"',
            "request": self.request,
        })
        self.assertIn('data-stream-url="http://localhost:5000/video_feed?a=1&amp;label=&quot;camera&quot;"', html)
        self.assertRegex(html, r'href="/monitoramento/"[^>]+aria-current="page"')
        self.assertIn("Uma câmera ao vivo. As demais são de demonstração.", html)
        self.assertEqual(html.count('"kind": "live"'), 1)
        self.assertEqual(html.count('"kind": "demo"'), 3)
