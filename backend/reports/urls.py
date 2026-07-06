from __future__ import annotations

from django.urls import path

from reports.controllers.auth_controller import LoginView, MeView
from reports.controllers.report_controller import (
    CollaboratorDetailView,
    CollaboratorListCreateView,
    CollaboratorSyncView,
    GenerateReportView,
    ReportDetailView,
    ReportExportHtmlView,
    ReportExportJsonView,
    ReportExportPdfView,
    ReportHistoryView,
    ReportOptionsView,
)


urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("reports/options/", ReportOptionsView.as_view(), name="report-options"),
    path("reports/", ReportHistoryView.as_view(), name="report-history"),
    path("reports/generate/", GenerateReportView.as_view(), name="report-generate"),
    path("reports/<uuid:pk>/", ReportDetailView.as_view(), name="report-detail"),
    path("reports/<uuid:pk>/export/json/", ReportExportJsonView.as_view(), name="report-json"),
    path("reports/<uuid:pk>/export/html/", ReportExportHtmlView.as_view(), name="report-html"),
    path("reports/<uuid:pk>/export/pdf/", ReportExportPdfView.as_view(), name="report-pdf"),
    path("collaborators/", CollaboratorListCreateView.as_view(), name="collaborator-list"),
    path("collaborators/sync/", CollaboratorSyncView.as_view(), name="collaborator-sync"),
    path("collaborators/<int:pk>/", CollaboratorDetailView.as_view(), name="collaborator-detail"),
]
