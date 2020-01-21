from datetime import date, datetime
from operator import attrgetter
import uuid

from cuser.models import AbstractCUser
from django import forms
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
import pydash as py_

from .constants import SCHOOLS


class User(AbstractCUser):
    def is_participant(self):
        return Participant.objects.filter(user=self).exists()


class GradeManager(models.Manager):
    def get_current(self, current=None):
        current_date = current or date.today()
        return self.filter(
            start_date__lte=current_date, end_date__gte=current_date
        ).first()

    def archive(self, current=None):
        current_date = current or date.today()
        return self.filter(end_date__lt=current_date)


def default_grade_school_year():
    current_year = date.today()
    return f"{current_year.year}/{current_year.year + 1}"


def default_grade_start():
    return date(date.today().year, 8, 1)


def default_grade_end():
    return date(date.today().year + 1, 7, 31)


class Grade(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school_year = models.CharField(
        verbose_name="Školní rok",
        max_length=50,
        null=False,
        db_index=True,
        unique=True,
        default=default_grade_school_year,
    )
    errata = models.TextField(verbose_name="Errata", null=False, blank=True)
    start_date = models.DateField(
        verbose_name="Začíná",
        null=False,
        blank=False,
        db_index=True,
        default=default_grade_start,
    )
    end_date = models.DateField(
        verbose_name="Končí",
        null=False,
        blank=False,
        db_index=True,
        default=default_grade_end,
    )

    objects = GradeManager()

    class Meta:
        verbose_name = "Ročník"
        verbose_name_plural = "Ročníky"
        ordering = ("-end_date",)

    @property
    def is_in_progress(self):
        return self.start_date <= date.today() <= self.end_date

    def __str__(self):
        return self.school_year

    def full_clean(self, *args, **kwargs):
        """Validate the grade.

        Make sure 'valid_through' does not overlap."""
        super().full_clean(*args, **kwargs)

        if self.start_date is not None and self.end_date is not None:
            g = (
                Grade.objects.filter(
                    models.Q(
                        start_date__lte=self.start_date, end_date__gte=self.start_date,
                    )
                    | models.Q(
                        start_date__lte=self.end_date, end_date__gte=self.end_date,
                    )
                )
                .exclude(pk=self.pk)
                .first()
            )

            if g:
                raise forms.ValidationError(
                    f"Datum konání se překrývá s ročníkem '{g}'."
                )

    def get_current_series(self):
        """Return first series that can still accept solution submissions from participants."""
        return (
            py_.chain(list(self.series.all()))
            .filter(attrgetter("accepts_solution_submissions"))
            .sort(key=attrgetter("submission_deadline"))
            .head()
            .value()
        )


class GradeSeries(models.Model):
    SERIES_CHOICES = (
        ("1", "1."),
        ("2", "2."),
        ("3", "3."),
        ("4", "4."),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grade = models.ForeignKey(
        Grade, verbose_name="Ročník", on_delete=models.CASCADE, related_name="series"
    )
    series = models.CharField(
        verbose_name="Série",
        max_length=1,
        choices=SERIES_CHOICES,
        null=False,
        db_index=True,
    )
    submission_deadline = models.DateTimeField(
        verbose_name="Deadline pro odeslání řešení", null=False
    )
    task_file = models.FileField(
        verbose_name="Brožura", upload_to="rocniky/zadani/", null=True, blank=True
    )
    results_published = models.BooleanField(
        verbose_name="Zveřejnit výsledky",
        null=False,
        blank=False,
        default=False,
        db_index=True,
    )

    class Meta:
        unique_together = ("grade", "series")
        verbose_name = "Série"
        verbose_name_plural = "Série"
        ordering = ("grade", "series")

    def __str__(self):
        return f"{self.get_series_display()} série"

    @property
    def accepts_solution_submissions(self):
        return self.task_file is not None and self.submission_deadline > datetime.now(
            self.submission_deadline.tzinfo
        )

    def calculate_results(self):
        """Calculate results for series.

        Adds detailed task listing for individual series tasks and a grand total with total score so far
        (this series and the previous ones).
        """
        applications = self.grade.applications.all()
        tasks = self.tasks.all()
        submissions = TaskSolutionSubmission.objects.filter(
            application__grade=self.grade, task__series__series__lte=self.series
        )

        scoring_dict = {
            a: {"by_tasks": {t: None for t in tasks}, "total": 0} for a in applications
        }

        def _find_application(app_id):
            return py_.find(applications, lambda a: a.pk == app_id)

        def _find_task(task_id):
            return py_.find(tasks, lambda t: t.pk == task_id)

        for s in submissions:
            a = _find_application(s.application_id)
            t = _find_task(s.task_id)

            scoring_dict[a]["by_tasks"][t] = s.score
            scoring_dict[a]["total"] += s.score or 0

        scoring = [
            (application, scores["by_tasks"], scores["total"])
            for application, scores in scoring_dict.items()
        ]

        return {
            "max_score": Task.objects.filter(
                series__grade=self.grade, series__series__lte=self.series
            ).aggregate(models.Sum("points"))["points__sum"],
            "listing": sorted(scoring, key=lambda row: row[2], reverse=True),
        }


class Task(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    series = models.ForeignKey(
        GradeSeries,
        verbose_name="Série",
        on_delete=models.PROTECT,
        related_name="tasks",
    )
    title = models.CharField(verbose_name="Název", max_length=150, null=False)
    points = models.PositiveIntegerField(
        verbose_name="Max. počet bodů",
        null=False,
        blank=False,
        validators=(MinValueValidator(1),),
    )

    class Meta:
        verbose_name = "Úloha"
        verbose_name_plural = "Úlohy"
        ordering = ("series", "title")
        permissions = (("solution_export", "Export odevzdaných úloh"),)

    def __str__(self):
        return self.title


class Participant(models.Model):
    COUNTRY_CHOICES = (
        ("other", "-- jiný --"),
        ("cz", "Česko"),
        ("sk", "Slovensko"),
    )
    GRADE_CHOICES = (
        ("4", "4."),
        ("3", "3."),
        ("2", "2."),
        ("1", "1."),
        ("l", "nižší"),
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="participant_profile",
    )

    phone = models.CharField(verbose_name="Telefon", max_length=20, null=True)
    street = models.CharField(verbose_name="Ulice", max_length=100, null=False)
    city = models.CharField(verbose_name="Obec", max_length=100, null=False)
    zip_code = models.CharField(verbose_name="PSČ", max_length=10, null=False)
    country = models.CharField(
        verbose_name="Stát", max_length=10, null=False, choices=COUNTRY_CHOICES
    )

    school = models.CharField(
        verbose_name="Škola", max_length=80, null=False, choices=SCHOOLS
    )
    school_year = models.CharField(
        verbose_name="Ročník", max_length=1, null=False, choices=GRADE_CHOICES,
    )

    school_alt_name = models.CharField(
        verbose_name="Název školy", max_length=80, null=True, blank=True
    )
    school_alt_street = models.CharField(
        verbose_name="Ulice školy", max_length=100, null=True, blank=True
    )
    school_alt_city = models.CharField(
        verbose_name="Obec školy", max_length=100, null=True, blank=True
    )
    school_alt_zip_code = models.CharField(
        verbose_name="PSČ školy", max_length=10, null=True, blank=True
    )

    applications = models.ManyToManyField(
        Grade,
        verbose_name="Přihlášky",
        related_name="participants",
        blank=True,
        through="GradeApplication",
    )

    class Meta:
        verbose_name = "Řešitel"
        verbose_name_plural = "Řešitelé"

    def __str__(self):
        return f"Profil účastníka pro <{self.user}>"

    def get_full_name(self):
        return f"{self.user.get_full_name() or self.user.email}"


class GradeApplication(models.Model):
    grade = models.ForeignKey(
        Grade, on_delete=models.CASCADE, related_name="applications"
    )
    participant = models.ForeignKey(Participant, on_delete=models.PROTECT)

    class Meta:
        verbose_name = "Přihláška do ročníku"
        verbose_name_plural = "Přihlášky do ročníku"

    def __str__(self):
        return f"Přihláška <{self.participant.user}> do ročníku <{self.grade}>"


class TaskSolutionSubmission(models.Model):
    application = models.ForeignKey(
        GradeApplication,
        verbose_name="Přihláška",
        null=False,
        blank=False,
        on_delete=models.CASCADE,
        related_name="solution_submissions",
    )
    task = models.ForeignKey(
        Task,
        verbose_name="Úloha",
        null=False,
        blank=False,
        on_delete=models.PROTECT,
        related_name="solution_submissions",
    )
    # If file is NULL, it means that the solution has been submitted by post
    file = models.FileField(
        verbose_name="Soubor s řešením",
        upload_to="rocniky/reseni/",
        null=True,
        blank=True,
    )
    score = models.DecimalField(
        verbose_name="Skóre", max_digits=5, decimal_places=2, null=True, blank=True
    )
    submitted_at = models.DateTimeField(verbose_name="Datum nahrání", auto_now_add=True)
    stickers = models.ManyToManyField(
        "Sticker", blank=True, related_name="solution_uses"
    )

    class Meta:
        verbose_name = "Odevzdané řešení"
        verbose_name_plural = "Odevzdaná řešení"
        permissions = (
            ("change_solution_submission_presence", "Úprava stavu odevzdání řešení"),
            ("scoring", "Bodování"),
        )

    def __str__(self):
        return f"Řešení <{self.task}> pro přihlášku <{self.application_id}>"


class Sticker(models.Model):
    title = models.CharField(
        verbose_name="Název", max_length=255, null=False, blank=False
    )
    description = models.TextField(verbose_name="Popis", null=True, blank=True)
    nr = models.PositiveSmallIntegerField(
        verbose_name="Číslo", null=False, db_index=True,
    )
    handpicked = models.BooleanField(
        verbose_name="Přiřazován ručně", default=True, null=False, db_index=True
    )
    uses = models.ManyToManyField(GradeApplication, blank=True, related_name="stickers")

    class Meta:
        verbose_name = "Nálepka"
        verbose_name_plural = "Nálepky"
        permissions = (("auto_assign_stickers", "Automatické nastavení nálepek"),)

    def __str__(self):
        return f"{self.nr} - {self.title}"


def sticker_auto_assignment(listing):
    """Replace sticker numbers in eligibility listing with real sticker objects."""
    sticker_nrs = (
        py_.py_(list(nrs) for application, nrs in listing).flatten().uniq().value()
    )
    stickers_by_nr = {s.nr: s for s in Sticker.objects.filter(nr__in=sticker_nrs)}

    def _replace_with_sticker_objs(listing_item):
        application, sticker_nrs = listing_item
        return (
            application,
            [stickers_by_nr[nr] for nr in sticker_nrs if nr in stickers_by_nr],
        )

    return py_.map_(listing, _replace_with_sticker_objs)


def sync_sticker_assignment(eligibility_listing):
    for application, stickers in eligibility_listing:
        for sticker in stickers:
            sticker.uses.add(application)


class EventManager(models.Manager):
    def future(self, current=None):
        current_date = current or date.today()
        return self.filter(end_date__gte=current_date)

    def past(self, current=None):
        current_date = current or date.today()
        return self.filter(end_date__lt=current_date)


class Event(models.Model):
    title = models.CharField(verbose_name="Název", max_length=150, null=False)
    description = models.TextField(verbose_name="Popis", null=False, blank=True)
    place = models.CharField(verbose_name="Místo konání", max_length=150, null=True)
    start_date = models.DateField(
        verbose_name="Začíná", null=False, blank=False, db_index=True,
    )
    end_date = models.DateField(
        verbose_name="Končí", null=False, blank=False, db_index=True,
    )
    capacity = models.PositiveSmallIntegerField(
        verbose_name="Doporučený max. počet účastníků", null=True, blank=True
    )
    enlistment_message = models.TextField(
        verbose_name="Zpráva po přihlášení", null=False, blank=True
    )
    attendees = models.ManyToManyField(User, verbose_name="Účastníci", blank=True)

    objects = EventManager()

    class Meta:
        verbose_name = "Akce"
        verbose_name_plural = "Akce"
        ordering = ("-start_date",)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse(
            "core:event_detail", kwargs={"pk": self.pk, "slug": slugify(self.title)}
        )
