from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.models import OvertimeEntry, WorkCalendarException
from reports.serializers import OvertimeEntrySerializer, WorkCalendarExceptionSerializer


class CalendarExceptionListCreateView(APIView):
    def get(self, request):
        items = WorkCalendarException.objects.prefetch_related("collaborators").all()
        month = request.query_params.get("month")
        if month and len(month) >= 7:
            year_s, month_s = month[:7].split("-", 1)
            items = items.filter(date__year=int(year_s), date__month=int(month_s))
        return Response(WorkCalendarExceptionSerializer(items, many=True).data)

    def post(self, request):
        serializer = WorkCalendarExceptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(WorkCalendarExceptionSerializer(item).data, status=201)


class CalendarExceptionDetailView(APIView):
    def patch(self, request, pk: int):
        item = get_object_or_404(WorkCalendarException, pk=pk)
        serializer = WorkCalendarExceptionSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(WorkCalendarExceptionSerializer(item).data)

    def delete(self, request, pk: int):
        item = get_object_or_404(WorkCalendarException, pk=pk)
        item.delete()
        return Response(status=204)


class OvertimeListCreateView(APIView):
    def get(self, request):
        items = OvertimeEntry.objects.select_related("collaborator").all()
        month = request.query_params.get("month")
        if month and len(month) >= 7:
            year_s, month_s = month[:7].split("-", 1)
            items = items.filter(date__year=int(year_s), date__month=int(month_s))
        return Response(OvertimeEntrySerializer(items, many=True).data)

    def post(self, request):
        serializer = OvertimeEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(OvertimeEntrySerializer(item).data, status=201)


class OvertimeDetailView(APIView):
    def patch(self, request, pk: int):
        item = get_object_or_404(OvertimeEntry, pk=pk)
        serializer = OvertimeEntrySerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(OvertimeEntrySerializer(item).data)

    def delete(self, request, pk: int):
        item = get_object_or_404(OvertimeEntry, pk=pk)
        item.delete()
        return Response(status=204)
