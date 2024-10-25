# *****************************************
# |docname| - definition of database models
# *****************************************
# In this file we define our SQLAlchemy data models. These get translated into relational database tables.
#
# Many of the models in this file were generated automatically for us by the ``sqlacodegen`` tool
# See `pypi for details <https://pypi.org/project/sqlacodegen/>`_   Although we are defining these using
# the declarative base style we will be using the SQLAlchemy Core for queries.  We are using
# SQLAlchemy 1.4.x in preparation for 2.0 and the more unified interface it provides for mixing
# declarative with core style queries.
#
# The models are created to be backward compatible with our current web2py implementation of
# Runestone.  Some decisions we would make differently but we won't be changing those things
# until we port the instructor interface to the FastAPI framework.
#
# Migrations
# ==========
# We use `Alembic <https://alembic.sqlalchemy.org/en/latest/>`_ for tracking database migration information.
# To create a new migration automatically after you have made changes to this file, run ``alembic revision --autogenerate -m "simple message"``
# this will generate a new file in ``alembic/versions``. To apply changes to the database run ``alembic upgrade head``.
#
# :index:`docs to write`: It is also possible...
#
# Imports
# =======
# These are listed in the order prescribed by `PEP 8`_.
#
# Standard library
# ----------------
import re
from typing import Dict, Type
from datetime import datetime

# Third-party imports
# -------------------
from pydantic import field_validator
from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Date,
    DateTime,
    JSON,
    Text,
    types,
    Float,
    inspect,
    LargeBinary,
    CHAR,
)
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql.schema import UniqueConstraint

# Local application imports
# -------------------------
from .async_session import Base
from rsptx.validation.schemas import BaseModelNone, sqlalchemy_to_pydantic


# Web2Py boolean type
# ===================
# Define a web2py-compatible Boolean type. See `custom types <http://docs.sqlalchemy.org/en/latest/core/custom_types.html>`_.
class Web2PyBoolean(types.TypeDecorator):
    impl = types.CHAR(1)
    python_type = bool
    # From the `docs <https://docs.sqlalchemy.org/en/14/core/custom_types.html#sqlalchemy.types.TypeDecorator.cache_ok>`_: "The requirements for cacheable elements is that they are hashable and also that they indicate the same SQL rendered for expressions using this type every time for a given cache value."
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value:
            return "T"
        elif value is None:
            return None
        elif not value:
            return "F"
        else:
            assert False, f"{value} is not T or F"

    def process_result_value(self, value, dialect):
        if value == "T":
            return True
        elif value == "F":
            return False
        elif value is None:
            return None
        else:
            assert False, f"{value} is not T or F"

    def copy(self, **kw):
        return Web2PyBoolean(self.impl.length)


# Schema Definition
# =================


# Provide a container to store information about each type of Runestone Component. While a namedtuple would be better, this can't be used since the fields aren't modifiable after creation; see the comment on `init_graders <init_graders>`.
class RunestoneComponentDict:
    def __init__(self, model: Type[Base], validator: Type[BaseModelNone]):
        self.grader = None
        self.model = model
        self.validator = validator


# Store this information in a dict whose key is the component's name, as a string.
runestone_component_dict: Dict[str, RunestoneComponentDict] = {}


# _`register_answer_table`: Provide a decorator for a class that populates this table.
def register_answer_table(
    sql_alchemy_cls: Type[Base],
) -> Type[Base]:
    global runestone_component_dict

    table_name = sql_alchemy_cls.__tablename__
    runestone_component_dict[table_name] = RunestoneComponentDict(
        sql_alchemy_cls,
        sqlalchemy_to_pydantic(sql_alchemy_cls),
    )
    return sql_alchemy_cls


# IdMixin
# -------
# Always name a table's ID field the same way.
class IdMixin:
    id = Column(Integer, primary_key=True)


# Useinfo
# -------
# This defines the useinfo table in the database. This table logs nearly every click
# generated by a student. It gets very large and needs a lot of indexes to keep Runestone
# from bogging down.
#
# User info logged by the `log_book_event endpoint`. See there for more info.
class Useinfo(Base, IdMixin):
    __tablename__ = "useinfo"
    __table_args__ = (Index("sid_divid_idx", "sid", "div_id"),)

    # _`timestamp`: when this entry was recorded by this webapp.
    timestamp = Column(DateTime, index=True, nullable=False)
    # _`sid`: TODO: The student id? (user) which produced this row.
    sid = Column(String(512), index=True, nullable=False)
    # The type of question (timed exam, fill in the blank, etc.).
    event = Column(String(512), index=True, nullable=False)
    # TODO: What is this? The action associated with this log entry?
    act = Column(Text, nullable=False)
    # _`div_id`: the ID of the question which produced this entry.
    div_id = Column(String(512), index=True, nullable=False)
    # _`course_id`: the Courses ``course_name`` **NOT** the ``id`` this row refers to. TODO: Use the ``id`` instead!
    course_id = Column(
        String(512), ForeignKey("courses.course_name"), index=True, nullable=False
    )
    # These are not currently in web2py but I'm going to add them
    ##chapter = Column(String, unique=False, index=False)
    ##sub_chapter = Column(String, unique=False, index=False)


UseinfoValidation = sqlalchemy_to_pydantic(Useinfo)


# Answers to specific question types
# ----------------------------------
class AnswerMixin(IdMixin):
    # See timestamp_.
    timestamp = Column(DateTime, nullable=False)
    # See div_id_.
    div_id = Column(String(512), index=True, nullable=False)
    # See sid_.
    sid = Column(String(512), index=True, nullable=False)

    # See course_name_. Mixins with foreign keys need `special treatment <http://docs.sqlalchemy.org/en/latest/orm/extensions/declarative/mixins.html#mixing-in-columns>`_.
    @declared_attr
    def course_name(cls):
        return Column(
            String(512), ForeignKey("courses.course_name"), index=True, nullable=False
        )

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in inspect(self).mapper.column_attrs}


@register_answer_table
class TimedExam(Base, AnswerMixin):
    __tablename__ = "timed_exam"
    # See the :ref:`timed exam endpoint parameters` for documentation on these columns..
    correct = Column(Integer, nullable=False)
    incorrect = Column(Integer, nullable=False)
    skipped = Column(Integer, nullable=False)
    time_taken = Column(Integer, nullable=False)
    # True if the ``act`` endpoint parameter was ``'reset'``; otherwise, False.
    reset = Column(Web2PyBoolean)


TimedExamValidator = sqlalchemy_to_pydantic(TimedExam)


# Like an AnswerMixin, but also has a boolean correct_ field.
class CorrectAnswerMixin(AnswerMixin):
    # _`correct`: True if this answer is correct.
    correct = Column(Web2PyBoolean, nullable=False)
    # Some question types (drag-n-drop, for example) don't provide this. A more accurate approach would be to specify this for each answer class, but I'm avoiding that extra work for now.
    percent = Column(Float)


# An answer to a multiple-choice question.
@register_answer_table
class MchoiceAnswers(Base, CorrectAnswerMixin):
    __tablename__ = "mchoice_answers"
    # _`answer`: The answer to this question. TODO: what is the format?
    answer = Column(String(50), nullable=False)
    __table_args__ = (
        Index(
            "mult_scd_idx",
            "div_id",
            "course_name",
            "sid",
        ),
    )


# An answer to a fill-in-the-blank question.
@register_answer_table
class FitbAnswers(Base, CorrectAnswerMixin):
    __tablename__ = "fitb_answers"
    # See answer_. TODO: what is the format?
    answer = Column(String(512), nullable=False)
    __table_args__ = (Index("idx_div_sid_course_fb", "sid", "div_id", "course_name"),)


# An answer to a drag-and-drop question.
@register_answer_table
class DragndropAnswers(Base, CorrectAnswerMixin):
    __tablename__ = "dragndrop_answers"
    # See answer_. TODO: what is the format?
    answer = Column(String(512), nullable=False)
    min_height = Column(Integer, nullable=False)
    __table_args__ = (Index("idx_div_sid_course_dd", "sid", "div_id", "course_name"),)


# An answer to a drag-and-drop question.
@register_answer_table
class ClickableareaAnswers(Base, CorrectAnswerMixin):
    __tablename__ = "clickablearea_answers"
    # See answer_. TODO: what is the format?
    answer = Column(String(512), nullable=False)
    __table_args__ = (Index("idx_div_sid_course_ca", "sid", "div_id", "course_name"),)


# An answer to a Parsons problem.
@register_answer_table
class ParsonsAnswers(Base, CorrectAnswerMixin):
    __tablename__ = "parsons_answers"
    # See answer_. TODO: what is the format?
    answer = Column(String(512), nullable=False)
    # _`source`: The source code provided by a student? TODO.
    source = Column(String(512), nullable=False)
    __table_args__ = (Index("parsons_scd_idx", "div_id", "course_name", "sid"),)


# An answer to a Code Lens problem.
@register_answer_table
class CodelensAnswers(Base, CorrectAnswerMixin):
    __tablename__ = "codelens_answers"
    # See answer_. TODO: what is the format?
    answer = Column(String(512), nullable=False)
    # See source_.
    source = Column(String(512), nullable=True)
    __table_args__ = (Index("idx_div_sid_course_cl", "sid", "div_id", "course_name"),)


@register_answer_table
class ShortanswerAnswers(Base, AnswerMixin):
    __tablename__ = "shortanswer_answers"
    # See answer_. TODO: what is the format?
    answer = Column(Text, nullable=False)
    __table_args__ = (Index("idx_div_sid_course_sa", "sid", "div_id", "course_name"),)


@register_answer_table
class UnittestAnswers(Base, CorrectAnswerMixin):
    __tablename__ = "unittest_answers"
    answer = Column(Text, nullable=True)
    passed = Column(Integer, nullable=False)
    failed = Column(Integer, nullable=False)
    __table_args__ = (Index("idx_div_sid_course_ut", "sid", "div_id", "course_name"),)


UnittestAnswersValidation = sqlalchemy_to_pydantic(UnittestAnswers)


# An answer to a fill-in-the-blank question.
@register_answer_table
class WebWorkAnswers(Base, CorrectAnswerMixin):
    __tablename__ = "webwork_answers"
    # See answer_. TODO: what is the format?
    answer = Column(JSON, nullable=False)
    __table_args__ = (Index("idx_div_sid_course_ww", "sid", "div_id", "course_name"),)


# An answer to a fill-in-the-blank question.
@register_answer_table
class MicroParsonsAnswers(Base, CorrectAnswerMixin):
    __tablename__ = "microparsons_answers"
    # See answer_. TODO: what is the format?
    answer = Column(JSON, nullable=False)
    __table_args__ = (Index("idx_div_sid_course_mp", "sid", "div_id", "course_name"),)


@register_answer_table
class LpAnswers(Base, AnswerMixin):
    __tablename__ = "lp_answers"
    # See answer_. A JSON string; see RunestoneComponents for details.
    answer = Column(Text, nullable=False)
    # A grade between 0 and 100. None means the student hasn't submitted an answer yet. This was added before the ``percent`` field most other question types now have; it serves the same role, but stores the answer as a percentage. (The ``percent`` field in other questions stores values between 0 and 1.)
    correct = Column(Float())
    __table_args__ = (Index("idx_div_sid_course_lp", "sid", "div_id", "course_name"),)


# Code
# ----
# The code table captures every run/change of the students code.  It is used to load
# the history slider of the activecode component.
#
class Code(Base, IdMixin):
    __tablename__ = "code"
    timestamp = Column(DateTime, unique=False, index=True, nullable=False)
    sid = Column(String(512), unique=False, index=True, nullable=False)
    acid = Column(
        String(512),
        unique=False,
        index=True,
        nullable=False,
    )  # unique identifier for a component
    course_id = Column(Integer, index=True, nullable=False)
    code = Column(Text, index=False, nullable=False)
    language = Column(Text, nullable=False)
    emessage = Column(Text, nullable=True)
    comment = Column(Text)
    edit_distance = Column(Integer)
    cps = Column(Float())


CodeValidator = sqlalchemy_to_pydantic(Code)


# Used for datafiles and storing questions and their suffix separately.
# this maybe redundant TODO: check before we port the api call to get
# a datafile
class SourceCode(Base, IdMixin):
    __tablename__ = "source_code"

    acid = Column(String(512), index=True, nullable=False)
    course_id = Column(String(512), index=True, nullable=False)
    includes = Column(String(512))
    available_files = Column(String(512))
    main_code = Column(Text, nullable=False)
    suffix_code = Column(Text)


SourceCodeValidator = sqlalchemy_to_pydantic(SourceCode)


# Courses
# -------
# Every Course in the runestone system must have an entry in this table
# the id column is really an artifact of the original web2py/pydal implementation of
# Runestone.  The 'real' primary key of this table is the course_name
# Defines either a base course (which must be manually added to the database) or a derived course created by an instructor.
class Courses(Base, IdMixin):
    __tablename__ = "courses"
    # _`course_name`: The name of this course.
    course_name = Column(String(512), unique=True, nullable=False)
    term_start_date = Column(Date, nullable=False)
    institution = Column(String(512), nullable=False)
    # _`base_course`: the course from which this course was derived. If this is a base course, this field is identical to the course_name_.
    base_course = Column(String(512), ForeignKey("courses.course_name"), nullable=False)
    python3 = Column(Web2PyBoolean, default=True)
    login_required = Column(Web2PyBoolean, nullable=False)
    allow_pairs = Column(Web2PyBoolean, nullable=False)
    student_price = Column(Integer)
    downloads_enabled = Column(Web2PyBoolean, nullable=False)
    courselevel = Column(String, nullable=False)
    institution = Column(String, nullable=False)
    # This is (hopefully) a temporary field to indicate that this book
    # should be served by the new bookserver
    new_server = Column(Web2PyBoolean, default=True)
    is_supporter = Column(Web2PyBoolean)
    state = Column(String(128))  # the US State in which the course is taught


CoursesValidator = sqlalchemy_to_pydantic(Courses)


# Authentication and Permissions
# ------------------------------
class AuthUser(Base, IdMixin):
    __tablename__ = "auth_user"
    username = Column(String(512), index=True, nullable=False, unique=True)
    first_name = Column(String(512), nullable=False)
    last_name = Column(String(512), nullable=False)
    email = Column(String(512), unique=False, nullable=False)
    password = Column(String(512), nullable=False)
    created_on = Column(DateTime(), nullable=False)
    modified_on = Column(DateTime(), nullable=False)
    registration_key = Column(String(512), nullable=False)
    reset_password_key = Column(String(512), nullable=False)
    registration_id = Column(String(512), nullable=False)
    course_id = Column(Integer, nullable=False)
    course_name = Column(String(512), nullable=False)
    active = Column(Web2PyBoolean, nullable=False)
    donated = Column(Web2PyBoolean, nullable=False)
    accept_tcp = Column(Web2PyBoolean, nullable=False)


BaseAuthUserValidator = sqlalchemy_to_pydantic(AuthUser)


class AuthUserValidator(BaseAuthUserValidator):  # type: ignore
    @field_validator("username")
    @classmethod
    def username_clear_of_css_characters(cls, v):
        if re.search(r"""[!"#$%&'()*+,./@:;<=>?[\]^`{|}~ ]""", v):
            pass
            # raise ValueError("username must not contain special characters")
        return v

    # TODO: restore the special character vaalidation after aging out legacy usernames
    # with special characters.  These *are* valid usernames because we allowed them to
    # be registered.  And we cannot take away someone's username in the middle of the course.
    ## So far the recommendation from Pydantic is to do async validation
    ## outside the validator proper as validators are not async
    ## @validator("username")
    ## def username_unique(cls, v):
    ##     if bookserver.crud.fetch_user(v):
    ##         raise ValueError("username must be unique")
    ##     return v


class AuthEvent(Base, IdMixin):
    __tablename__ = "auth_event"

    time_stamp = Column(DateTime)
    client_ip = Column(String(512))
    user_id = Column(ForeignKey("auth_user.id", ondelete="CASCADE"))
    origin = Column(String(512))
    description = Column(Text)


class AuthGroup(Base, IdMixin):
    __tablename__ = "auth_group"

    role = Column(String(512))
    description = Column(Text)


class AuthMembership(Base, IdMixin):
    __tablename__ = "auth_membership"

    user_id = Column(ForeignKey("auth_user.id", ondelete="CASCADE"))
    group_id = Column(ForeignKey("auth_group.id", ondelete="CASCADE"))


class CourseInstructor(Base, IdMixin):
    __tablename__ = "course_instructor"
    __table_args__ = (Index("c_i_idx", "course", "instructor"),)

    course = Column(
        Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    instructor = Column(
        Integer,
        ForeignKey("auth_user.id", ondelete="CASCADE"),
        nullable=False,
    )
    verified = Column(Web2PyBoolean)
    paid = Column(Web2PyBoolean)


CourseInstructorValidator = sqlalchemy_to_pydantic(CourseInstructor)


# Enrollments
# -----------
#
# Users may be enrolled in more than one course. This table tracks
# all of their enrollments
class UserCourse(Base, IdMixin):
    __tablename__ = "user_courses"

    user_id = Column(ForeignKey("auth_user.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)


# Assignments and Questions
# -------------------------


class Question(Base, IdMixin):
    __tablename__ = "questions"
    __table_args__ = (
        UniqueConstraint("name", "base_course"),
        Index("chap_subchap_idx", "chapter", "subchapter"),
    )

    base_course = Column(String(512), nullable=False, index=True)
    name = Column(String(512), nullable=False, index=True)
    chapter = Column(String(512), index=True, nullable=False)
    subchapter = Column(String(512), index=True, nullable=False)
    author = Column(String(512))
    question = Column(Text)  # contains the question source text
    timestamp = Column(DateTime, nullable=False)
    question_type = Column(String(512), nullable=False)
    is_private = Column(Web2PyBoolean)
    htmlsrc = Column(Text)
    autograde = Column(String(512))
    practice = Column(Web2PyBoolean)
    topic = Column(String(512))
    feedback = Column(Text)
    from_source = Column(Web2PyBoolean, nullable=False)
    review_flag = Column(Web2PyBoolean, default=False)
    qnumber = Column(String(512))
    optional = Column(Web2PyBoolean)
    description = Column(Text)
    difficulty = Column(Float(53))
    pct_on_first = Column(Float(53))
    mean_clicks_to_correct = Column(Float(53))
    question_json = Column(JSON)  # contains the JSON representation of the question
    owner = Column(
        String(512)
    )  # username of the owner of the question (Author could be any name)
    tags = Column(String(512))  # comma separated list of tags


QuestionValidator = sqlalchemy_to_pydantic(Question)


class Tag(Base, IdMixin):
    __tablename__ = "tags"

    tag_name = Column(String(512), unique=True)


class QuestionTag(Base, IdMixin):
    __tablename__ = "question_tags"

    question_id = Column(
        ForeignKey("questions.id", ondelete="CASCADE", onupdate="CASCADE")
    )
    tag_id = Column(ForeignKey("tags.id", ondelete="CASCADE", onupdate="CASCADE"))


class Assignment(Base, IdMixin):
    __tablename__ = "assignments"
    __table_args__ = (
        Index("assignments_name_course_idx", "name", "course", unique=True),
    )

    course = Column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    name = Column(String(512), nullable=False)
    points = Column(Integer, default=0)
    released = Column(Web2PyBoolean, nullable=False)
    description = Column(Text)
    duedate = Column(DateTime, nullable=False)
    # visible = Column(Web2PyBoolean, nullable=False)
    visible_on = Column(DateTime, default=datetime.utcnow)
    threshold_pct = Column(Float(53))
    allow_self_autograde = Column(Web2PyBoolean)
    is_timed = Column(Web2PyBoolean)
    time_limit = Column(Integer)
    from_source = Column(Web2PyBoolean, nullable=False)
    nofeedback = Column(Web2PyBoolean)
    nopause = Column(Web2PyBoolean)
    is_peer = Column(Web2PyBoolean, default=False)
    current_index = Column(Integer, default=0)
    enforce_due = Column(Web2PyBoolean)
    peer_async_visible = Column(Web2PyBoolean, default=False)
    kind = Column(String(128))


AssignmentValidator = sqlalchemy_to_pydantic(Assignment)


class AssignmentQuestion(Base, IdMixin):
    __tablename__ = "assignment_questions"

    assignment_id = Column(
        ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id = Column(
        ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    points = Column(Integer, nullable=False)
    timed = Column(Web2PyBoolean)
    autograde = Column(String(512), nullable=False)
    which_to_grade = Column(String(512), nullable=False)
    reading_assignment = Column(Web2PyBoolean)
    sorting_priority = Column(Integer, nullable=False)
    activities_required = Column(
        Integer
    )  # only reading assignments will have this populated


AssignmentQuestionValidator = sqlalchemy_to_pydantic(AssignmentQuestion)


# Grading
# -------
# The QuestionGrade table holds the score and any comments for a particular
# student,question,course triple
# TODO: this actually seems wrong -- it should be student,question,assignment
# otherwise a student can only have a single grade for a particular question
# what if an instructor assigns the same question more than once??
class QuestionGrade(Base, IdMixin):
    __tablename__ = "question_grades"
    __table_args__ = (
        Index(
            "question_grades_key",
            "div_id",
            "course_name",
            "sid",
            unique=True,
        ),
    )

    sid = Column(String(512), nullable=False, index=True)
    course_name = Column(String(512), nullable=False, index=True)
    div_id = Column(String(512), nullable=False, index=True)
    # Manually-graded questions may be unscored (a NULL score).
    score = Column(Float(53))
    comment = Column(Text, nullable=True)
    deadline = Column(DateTime)
    # Grades before the improved autograded and manually-scored grades lack this. Since it can refer to an ID from many different tables, don't make it a constraint.
    answer_id = Column(Integer)


QuestionGradeValidator = sqlalchemy_to_pydantic(QuestionGrade)


# The Grade table holds the grade for an entire assignment
class Grade(Base, IdMixin):
    __tablename__ = "grades"
    __table_args__ = (
        UniqueConstraint("auth_user", "assignment"),
        Index("user_assign_unique_idx", "auth_user", "assignment"),
    )

    auth_user = Column(
        ForeignKey("auth_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment = Column(
        ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # If all questions in the assignment don't have a score, this won't either.
    score = Column(Float(53))
    manual_total = Column(Web2PyBoolean, nullable=False)
    # Not all grades will be reportable via LTI.
    lis_result_sourcedid = Column(String(1024))
    lis_outcome_url = Column(String(1024))
    is_submit = Column(String(512))


GradeValidator = sqlalchemy_to_pydantic(Grade)


# Book Structure Tables
# ---------------------
class Chapter(Base, IdMixin):
    __tablename__ = "chapters"

    chapter_name = Column(String(512), nullable=False)
    course_id = Column(String(512), index=True, nullable=False)
    chapter_label = Column(String(512), nullable=False)
    chapter_num = Column(Integer, nullable=False)


ChapterValidator = sqlalchemy_to_pydantic(Chapter)


class SubChapter(Base, IdMixin):
    __tablename__ = "sub_chapters"

    sub_chapter_name = Column(String(512), nullable=False)
    chapter_id = Column(
        ForeignKey("chapters.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sub_chapter_label = Column(String(512), index=True, nullable=False)
    skipreading = Column(Web2PyBoolean, nullable=False)
    sub_chapter_num = Column(Integer, nullable=False)


SubChapterValidator = sqlalchemy_to_pydantic(SubChapter)


# Tracking User Progress
# ----------------------
class UserSubChapterProgress(Base, IdMixin):
    __tablename__ = "user_sub_chapter_progress"

    user_id = Column(ForeignKey("auth_user.id", ondelete="CASCADE"), index=True)
    chapter_id = Column(String(512), index=True, nullable=False)
    sub_chapter_id = Column(String(512), index=True, nullable=False)
    # Initial values for this don't have dates.
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    status = Column(Integer, nullable=False)
    # Older courses lack this; all newer courses should have one.
    course_name = Column(String(512), index=True)


UserSubChapterProgressValidator = sqlalchemy_to_pydantic(UserSubChapterProgress)


class UserChapterProgress(Base, IdMixin):
    __tablename__ = "user_chapter_progress"

    user_id = Column(String(512), nullable=False)
    chapter_id = Column(String(512), nullable=False)
    # Initial values for this don't have dates.
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    status = Column(Integer, nullable=False)


UserChapterProgressValidator = sqlalchemy_to_pydantic(UserChapterProgress)


class UserState(Base, IdMixin):
    __tablename__ = "user_state"

    user_id = Column(
        ForeignKey("auth_user.id", ondelete="CASCADE"), index=True, nullable=False
    )
    course_name = Column(String(512), index=True, nullable=False)
    last_page_url = Column(String(512))
    last_page_hash = Column(String(512))
    last_page_chapter = Column(String(512))
    last_page_subchapter = Column(String(512))
    last_page_scroll_location = Column(Integer)
    last_page_accessed_on = Column(DateTime)


UserStateValidator = sqlalchemy_to_pydantic(UserState)

# Tables used by the ``selectquestion`` directive
# -----------------------------------------------


class SubChapterTaught(Base, IdMixin):
    __tablename__ = "sub_chapter_taught"

    course_name = Column(String(512))
    chapter_label = Column(String(512))
    sub_chapter_label = Column(String(512))
    teaching_date = Column(Date)


class UserExperiment(Base, IdMixin):
    __tablename__ = "user_experiment"

    experiment_id = Column(String(512), nullable=False)
    sid = Column(String(512), nullable=False)
    exp_group = Column(Integer, nullable=False)


UserExperimentValidator = sqlalchemy_to_pydantic(UserExperiment)


class SelectedQuestion(Base, IdMixin):
    __tablename__ = "selected_questions"
    __table_args__ = (Index("selector_sid_unique", "selector_id", "sid"),)

    selector_id = Column(String(512), nullable=False)
    sid = Column(String(512), nullable=False)
    selected_id = Column(String(512), nullable=False)
    points = Column(Integer, nullable=False, default=0)
    competency = Column(String(512), nullable=True)


SelectedQuestionValidator = sqlalchemy_to_pydantic(SelectedQuestion)


class Competency(Base, IdMixin):
    __tablename__ = "competency"
    __table_args__ = (Index("q_comp_unique", "question", "competency"),)

    question = Column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    competency = Column(String(512), nullable=False)
    is_primary = Column(Web2PyBoolean, nullable=False)
    question_name = Column(String(512), nullable=False)


# Course Parameters
# -----------------
class CourseAttribute(Base, IdMixin):
    __tablename__ = "course_attributes"
    __table_args__ = (Index("course_attr_idx", "course_id", "attr"),)

    course_id = Column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    attr = Column(String(512), nullable=False)
    value = Column(Text, nullable=False)


class CourseLtiMap(Base, IdMixin):
    __tablename__ = "course_lti_map"

    lti_id = Column(Integer, nullable=False)
    course_id = Column(Integer, nullable=False)


class LtiKey(Base, IdMixin):
    __tablename__ = "lti_keys"

    consumer = Column(String(512), nullable=False)
    secret = Column(String(512), nullable=False)
    application = Column(String(512), nullable=False)


class Payment(Base, IdMixin):
    __tablename__ = "payments"

    user_courses_id = Column(
        ForeignKey("user_courses.id", ondelete="CASCADE"), nullable=False
    )
    charge_id = Column(String(255), nullable=False)


# Tracking Errors in a multi server configuration
#
class TraceBack(Base, IdMixin):
    __tablename__ = "traceback"

    traceback = Column(Text, nullable=False)
    timestamp = Column(DateTime)
    err_message = Column(String(512))
    path = Column(String(1024))
    query_string = Column(String(512))
    post_body = Column(String(1024))
    hash = Column(String(128))
    hostname = Column(String(128))


class Library(Base, IdMixin):
    __tablename__ = "library"
    title = Column(String(512), nullable=False)
    subtitle = Column(String(512))
    description = Column(Text)
    authors = Column(Text)
    shelf_section = Column(String(512))
    basecourse = Column(
        String(512), ForeignKey("courses.course_name"), nullable=False, unique=True
    )
    source_path = Column(String(512))  # path to the book source relative to BOOK_PATH/
    build_system = Column(String(20))
    target = Column(String(128))  # the target for the PreTeXt build system
    for_classes = Column(Web2PyBoolean)
    is_visible = Column(Web2PyBoolean, default="T")
    github_url = Column(String(512))
    main_page = Column(String(512), default="index.html")
    last_build = Column(DateTime)
    github_url = Column(String(255))
    social_url = Column(String(255))  # link to group for instructors
    default_language = Column(String(20))


LibraryValidator = sqlalchemy_to_pydantic(Library)


class BookAuthor(Base):
    __tablename__ = "book_author"
    # See https://stackoverflow.com/questions/28047027/sqlalchemy-not-find-table-for-creating-foreign-key
    # for why we use a string to specify the foreign key for author
    author = Column(
        String(512), ForeignKey("auth_user.username"), primary_key=True, nullable=False
    )
    book = Column(
        String(50), ForeignKey("library.basecourse"), primary_key=True, nullable=False
    )


class EditorBasecourse(Base, IdMixin):
    __tablename__ = "editor_basecourse"
    __table_args__ = (UniqueConstraint("editor", "base_course"),)
    editor = Column(ForeignKey("auth_user.id", ondelete="CASCADE"))
    base_course = Column(String(512))


# Tables for practice feature
#
class CoursePractice(Base, IdMixin):
    __tablename__ = "course_practice"
    auth_user_id = Column(ForeignKey("auth_user.id", ondelete="CASCADE"))
    course_name = Column(String(512))
    start_date = Column(Date)
    end_date = Column(Date)
    max_practice_days = Column(Integer)
    max_practice_questions = Column(Integer)
    day_points = Column(Float(53))
    question_points = Column(Float(53))
    questions_to_complete_day = Column(Integer)
    graded = Column(Integer)
    spacing = Column(Integer)
    interleaving = Column(Integer)
    flashcard_creation_method = Column(Integer)


CoursePracticeValidator = sqlalchemy_to_pydantic(CoursePractice)


class UserTopicPractice(Base, IdMixin):
    __tablename__ = "user_topic_practice"

    user_id = Column(ForeignKey("auth_user.id", ondelete="CASCADE"))
    course_name = Column(String(512))
    chapter_label = Column(String(512))
    sub_chapter_label = Column(String(512))
    question_name = Column(String(512))
    i_interval = Column(Integer, nullable=False)
    e_factor = Column(Float(53), nullable=False)
    last_presented = Column(DateTime)
    last_completed = Column(DateTime)
    creation_time = Column(DateTime)
    q = Column(Integer, nullable=False, default=0)
    next_eligible_date = Column(Date)
    timezoneoffset = Column(Integer)


UserTopicPracticeValidator = sqlalchemy_to_pydantic(UserTopicPractice)


class UserTopicPracticeCompletion(Base, IdMixin):
    __tablename__ = "user_topic_practice_completion"

    user_id = Column(ForeignKey("auth_user.id", ondelete="CASCADE", onupdate="CASCADE"))
    course_name = Column(String(512))
    practice_completion_date = Column(Date)


class UserTopicPracticeFeedback(Base, IdMixin):
    __tablename__ = "user_topic_practice_feedback"

    user_id = Column(ForeignKey("auth_user.id", ondelete="CASCADE", onupdate="CASCADE"))
    course_name = Column(String(512))
    feedback = Column(String(512))
    response_time = Column(DateTime)
    timezoneoffset = Column(Integer)


class UserTopicPracticeLog(Base, IdMixin):
    __tablename__ = "user_topic_practice_log"

    user_id = Column(ForeignKey("auth_user.id", ondelete="CASCADE", onupdate="CASCADE"))
    course_name = Column(String(512))
    chapter_label = Column(String(512))
    sub_chapter_label = Column(String(512))
    question_name = Column(String(512))
    i_interval = Column(Integer, nullable=False)
    e_factor = Column(Float(53), nullable=False)
    q = Column(Integer, nullable=False, default=-1)
    trials_num = Column(Integer, nullable=False)
    available_flashcards = Column(Integer, nullable=False, default=-1)
    start_practice = Column(DateTime)
    end_practice = Column(DateTime)
    timezoneoffset = Column(Integer)
    next_eligible_date = Column(Date)


class UserTopicPracticeSurvey(Base, IdMixin):
    __tablename__ = "user_topic_practice_survey"

    user_id = Column(ForeignKey("auth_user.id", ondelete="CASCADE", onupdate="CASCADE"))
    course_name = Column(String(512))
    like_practice = Column(String(512))
    response_time = Column(DateTime)
    timezoneoffset = Column(Integer)


# It is very unclear how much this table is actually used.
# It may only be used in the case of practice plus the LTI integration
class PracticeGrade(Base, IdMixin):
    __tablename__ = "practice_grades"

    auth_user = Column(ForeignKey("auth_user.id", ondelete="CASCADE"))
    course_name = Column(String(512))
    score = Column(Float(53))
    lis_result_sourcedid = Column(String(512))
    lis_outcome_url = Column(String(512))


# TODO: migrate away from this stuff below in author server

# engine = create_engine(os.environ["DEV_DBURL"])
# Session = sessionmaker(expire_on_commit=False)
# engine.connect()
# Session.configure(bind=engine)
# meta = MetaData()
#
# # Create table objects from database metadata that we do not control but want to use
# # in this application.
# auth_user = Table("auth_user", meta, autoload=True, autoload_with=engine)
# courses = Table("courses", meta, autoload=True, autoload_with=engine)
# library = Table("library", meta, autoload=True, autoload_with=engine)
# course_instructor = Table(
#     "course_instructor", meta, autoload=True, autoload_with=engine
# )


class InvoiceRequest(Base, IdMixin):
    __tablename__ = "invoice_request"

    timestamp = Column(DateTime)
    sid = Column(String(512))
    course_name = Column(String(512))
    email = Column(String(512))
    amount = Column(Float)
    processed = Column(Web2PyBoolean)


class Web2pySessionRunestone(Base, IdMixin):
    __tablename__ = "web2py_session_runestone"

    locked = Column(CHAR(1))
    client_ip = Column(String(64))
    created_datetime = Column(DateTime)
    modified_datetime = Column(DateTime)
    unique_key = Column(String(64))
    session_data = Column(LargeBinary)
