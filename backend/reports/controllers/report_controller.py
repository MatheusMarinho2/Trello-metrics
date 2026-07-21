from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.generics import RetrieveDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.models import Collaborator, GeneratedReport, ProjectSystem
from reports.serializers import (
    CollaboratorSerializer,
    CollaboratorSyncSerializer,
    GeneratedReportDetailSerializer,
    GeneratedReportListSerializer,
    ProjectSystemSerializer,
    ReportGenerationSerializer,
)
from reports.services.export_service import ReportExportService
from reports.services.options_service import report_options
from reports.services.report_generation_service import ReportGenerationService
from reports.services.trello_snapshot_service import (
    sync_collaborators_from_saved_reports,
    sync_collaborators_from_trello,
    sync_systems_from_trello,
)


class ReportOptionsView(APIView):
    def get(self, request):
        return Response(report_options())


class ReportHistoryView(APIView):
    def get(self, request):
        reports = GeneratedReport.objects.select_related("trello_snapshot").all()
        report_type = request.query_params.get("report_type")
        if report_type:
            reports = reports.filter(report_type=report_type)
        reports = reports[:50]
        return Response(GeneratedReportListSerializer(reports, many=True).data)

    def delete(self, request):
        reports = GeneratedReport.objects.all()
        report_type = request.query_params.get("report_type")
        if report_type:
            reports = reports.filter(report_type=report_type)
        deleted, _ = reports.delete()
        return Response({"deleted": deleted}, status=200)


class GenerateReportView(APIView):
    def post(self, request):
        serializer = ReportGenerationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = ReportGenerationService().generate(
            serializer.to_config(),
            created_by=request.user.username,
        )
        return Response(GeneratedReportDetailSerializer(report).data, status=201)


class ReportDetailView(RetrieveDestroyAPIView):
    queryset = GeneratedReport.objects.all()
    serializer_class = GeneratedReportDetailSerializer


class ReportExportJsonView(APIView):
    def get(self, request, pk):
        report = get_object_or_404(GeneratedReport, pk=pk)
        return ReportExportService().json_response(report)


class ReportExportPdfView(APIView):
    def get(self, request, pk):
        report = get_object_or_404(GeneratedReport, pk=pk)
        return ReportExportService().pdf_response(report)


class ReportExportHtmlView(APIView):
    def get(self, request, pk):
        report = get_object_or_404(GeneratedReport, pk=pk)
        return ReportExportService().html_response(report)


class CollaboratorSyncView(APIView):
    def post(self, request):
        serializer = CollaboratorSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = sync_collaborators_from_trello(
                board_id=data.get("board_id") or "",
                api_key=data.get("api_key") or "",
                token=data.get("token") or "",
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=502)

        collaborators = result.pop("collaborators")
        return Response(
            {
                **result,
                "collaborators": CollaboratorSerializer(collaborators, many=True).data,
            }
        )


class CollaboratorListCreateView(APIView):
    def get(self, request):
        sync_collaborators_from_saved_reports()
        collaborators = Collaborator.objects.all()
        return Response(CollaboratorSerializer(collaborators, many=True).data)

    def post(self, request):
        serializer = CollaboratorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        collaborator = serializer.save(source="manual")
        return Response(CollaboratorSerializer(collaborator).data, status=201)


class CollaboratorDetailView(APIView):
    def patch(self, request, pk):
        collaborator = get_object_or_404(Collaborator, pk=pk)
        serializer = CollaboratorSerializer(
            collaborator,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        collaborator = serializer.save()
        return Response(CollaboratorSerializer(collaborator).data)

    def delete(self, request, pk):
        collaborator = get_object_or_404(Collaborator, pk=pk)
        collaborator.active = False
        collaborator.save(update_fields=["active", "updated_at"])
        return Response(CollaboratorSerializer(collaborator).data)


class ProjectSystemSyncView(APIView):
    def post(self, request):
        serializer = CollaboratorSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = sync_systems_from_trello(
                board_id=data.get("board_id") or "",
                api_key=data.get("api_key") or "",
                token=data.get("token") or "",
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=502)

        systems = result.pop("systems")
        return Response(
            {
                **result,
                "systems": ProjectSystemSerializer(systems, many=True).data,
            }
        )


class ProjectSystemListCreateView(APIView):
    def get(self, request):
        systems = ProjectSystem.objects.all()
        return Response(ProjectSystemSerializer(systems, many=True).data)

    def post(self, request):
        serializer = ProjectSystemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        system = serializer.save(source="manual")
        return Response(ProjectSystemSerializer(system).data, status=201)


class ProjectSystemDetailView(APIView):
    def patch(self, request, pk):
        system = get_object_or_404(ProjectSystem, pk=pk)
        serializer = ProjectSystemSerializer(system, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        system = serializer.save()
        return Response(ProjectSystemSerializer(system).data)

    def delete(self, request, pk):
        system = get_object_or_404(ProjectSystem, pk=pk)
        system.active = False
        system.save(update_fields=["active", "updated_at"])
        return Response(ProjectSystemSerializer(system).data)
