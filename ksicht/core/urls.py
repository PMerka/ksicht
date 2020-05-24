from django.contrib.auth.decorators import permission_required
from django.urls import path
from django.views.generic import DetailView, ListView

from . import models, views


app_name = "core"


urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("aktualni-rocnik/", views.CurrentGradeView.as_view(), name="current_grade"),
    path(
        "archiv-rocniku/",
        ListView.as_view(
            queryset=models.Grade.objects.archive().prefetch_related(
                "series__attachments"
            ),
            template_name="core/grade_archive.html",
            paginate_by=10,
        ),
        name="grade_archive",
    ),
    path("akce/", views.EventListView.as_view(paginate_by=10), name="event_listing",),
    path(
        "akce/<int:pk>-<slug:slug>/",
        views.EventDetailView.as_view(),
        name="event_detail",
    ),
    path(
        "akce/<int:pk>-<slug:slug>/prihlasit-se/",
        views.EventEnlistView.as_view(),
        name="event_enlist",
    ),
    path(
        "akce/<int:pk>-<slug:slug>/export-ucastniku/",
        permission_required("core.export_event_attendees")(
            views.EventAttendeesExportView.as_view()
        ),
        name="event_attendees_export",
    ),
    path("lide/", views.PeopleView.as_view(), name="people",),
    path(
        "aktualni-rocnik/prihlasit-se/",
        views.CurrentGradeApplicationView.as_view(),
        name="current_grade_application",
    ),
    path(
        "aktualni-rocnik/odevzdat-reseni/",
        views.SolutionSubmitView.as_view(),
        name="solution_submit",
    ),
    path(
        "rocniky/<pk>/",
        permission_required("core.view_grade")(
            DetailView.as_view(
                template_name="core/manage/grade_detail.html",
                queryset=models.Grade.objects.all(),
            )
        ),
        name="grade_detail",
    ),
    path(
        "rocniky/<pk>/export-vysledku/",
        permission_required("core.view_grade")(views.GradeResultsExportView.as_view()),
        name="grade_results_export",
    ),
    path(
        "rocniky/<grade_id>/serie/<pk>/",
        permission_required("core.view_gradeseries")(views.SeriesDetailView.as_view()),
        name="series_detail",
    ),
    path(
        "rocniky/<grade_id>/serie/<pk>/vysledkova-listina/",
        views.SeriesResultsView.as_view(),
        name="series_results",
    ),
    path(
        "rocniky/<grade_id>/serie/<series_id>/odevzdana-reseni/",
        views.SubmissionOverview.as_view(),
        name="series_submission_overview",
    ),
    path(
        "rocniky/<grade_id>/serie/<pk>/nalepky/",
        permission_required("core.view_gradeseries")(
            views.StickerAssignmentOverview.as_view(),
        ),
        name="series_sticker_assignment_overview",
    ),
    path(
        "rocniky/<grade_id>/serie/<pk>/obalky-se-zadanim/",
        permission_required("core.series_envelopes_printout")(
            views.SeriesTaskEnvelopesPrintout.as_view()
        ),
        name="series_task_envelopes_printout",
    ),
    path(
        "rocniky/<grade_id>/serie/<pk>/obalky-s-resenim/",
        permission_required("core.series_envelopes_printout")(
            views.SeriesSolutionEnvelopesPrintout.as_view()
        ),
        name="series_solution_envelopes_printout",
    ),
    path(
        "rocniky/<grade_id>/bodovani/<task_id>/",
        views.ScoringView.as_view(),
        name="task_scoring",
    ),
    path(
        "rocniky/<grade_id>/export/<task_id>/",
        views.SolutionExportView.as_view(),
        name="task_solution_export",
    ),
]
