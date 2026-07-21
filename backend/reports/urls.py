from __future__ import annotations

from django.urls import path

from reports.controllers.auth_controller import LoginView, MeView
from reports.controllers.calendar_controller import (
    CalendarExceptionDetailView,
    CalendarExceptionListCreateView,
    OvertimeDetailView,
    OvertimeListCreateView,
)
from reports.controllers.report_controller import (
    CollaboratorDetailView,
    CollaboratorListCreateView,
    CollaboratorSyncView,
    GenerateReportView,
    ProjectSystemDetailView,
    ProjectSystemListCreateView,
    ProjectSystemSyncView,
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
    path("systems/", ProjectSystemListCreateView.as_view(), name="system-list"),
    path("systems/sync/", ProjectSystemSyncView.as_view(), name="system-sync"),
    path("systems/<int:pk>/", ProjectSystemDetailView.as_view(), name="system-detail"),
    path("calendar/exceptions/", CalendarExceptionListCreateView.as_view(), name="calendar-exceptions"),
    path("calendar/exceptions/<int:pk>/", CalendarExceptionDetailView.as_view(), name="calendar-exception-detail"),
    path("calendar/overtime/", OvertimeListCreateView.as_view(), name="calendar-overtime"),
    path("calendar/overtime/<int:pk>/", OvertimeDetailView.as_view(), name="calendar-overtime-detail"),
]
