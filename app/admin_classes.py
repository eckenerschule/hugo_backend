from flask_admin.contrib.pymongo.filters import BasePyMongoFilter
from flask_admin.contrib.pymongo import ModelView, filters
from flask_admin.model.fields import InlineFormField, InlineFieldList
from flask_admin.actions import action
from flask_admin.babel import lazy_gettext
from flask_admin.form import Select2Widget
from bson.datetime_ms import DatetimeMS
from bson.objectid import ObjectId
from flask_admin import expose
from markupsafe import Markup
from datetime import datetime
from wtforms import form, fields, validators
from flask import flash, request

import flask_login as login
import threading
import os

from .mongodb_connection import MongoDBConnection


mongodb_lock = threading.Lock()


def write_log(msg: str):
    path = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
    print(msg)
    # with open(
    #     os.path.join(path, "log.txt"), "a", encoding="utf-8", newline="\n"
    # ) as file:
    #     log_msg = f"""{datetime.now().strftime("%Y-%m-%d, %H:%M:%S")}: {msg}\n"""
    #     file.write(log_msg)
    #     file.close()


# ============================================= Filter ==========================================================
# Create user model.
class User(login.UserMixin):
    id: str = ""
    username: str = ""
    password: str = ""
    is_admin: bool = False

    @property
    def has_admin_powers(self):
        return self.is_admin

    def __init__(self, data: dict):
        self.id = str(data["_id"])
        self.username = data["username"]
        self.password = data["password"]
        self.is_admin = data["is_admin"]


# ============================================= Filter ==========================================================
class DateGreater(BasePyMongoFilter):
    def apply(self, query, value):
        print(f"Value: '{value}' - type: '{type(value)}'")
        try:
            value = datetime.strptime(value, "%Y-%m-%d")
            value = DatetimeMS(value)
        except ValueError:
            value = 0
        query.append({self.column: {"$gt": value}})
        return query

    def operation(self):
        return lazy_gettext("greater than")


class DateSmaller(BasePyMongoFilter):
    def apply(self, query, value):
        print(f"Value: '{value}' - type: '{type(value)}'")
        try:
            value = datetime.strptime(value, "%Y-%m-%d")
            value = DatetimeMS(value)
        except ValueError:
            value = 0
        query.append({self.column: {"$lt": value}})
        return query

    def operation(self):
        return lazy_gettext("smaller than")


# ============================================= View & Form classes =============================================
class MessageForm(form.Form):
    message = fields.StringField("Message")
    response = fields.StringField("Response")
    tag = fields.StringField("Tag")

    source_ids = InlineFieldList(fields.StringField())


class Chat_HistoryForm(form.Form):
    start_message = fields.StringField("Start_Message")
    description = fields.StringField("Description")
    date = fields.DateTimeField("Date")

    subjects = InlineFieldList(fields.StringField())
    messages = InlineFieldList(InlineFormField(MessageForm))


class Chat_HistoryView(ModelView):
    column_list = (
        "description",
        "date",
    )
    column_sortable_list = ("date",)

    column_filters = (
        filters.FilterLike("description", "Description"),
        filters.FilterNotLike("description", "Description"),
        filters.FilterLike("date", "Date"),
        filters.FilterNotLike("date", "Date"),
        DateGreater("date", "Date"),
        DateSmaller("date", "Date"),
    )

    column_details_list = (
        "description",
        "date",
        "subjects",
        "start_message",
        "messages",
    )

    def date_formatter(self, content, model, name):
        return model[name].date()

    def subjects_formatter(self, content, model, name):
        # Grab subjects
        sub_query = {"_id": {"$in": [sub for sub in model[name]]}}
        sub_cursor = self.sub_coll.find(sub_query)
        subjects = [x for x in sub_cursor]

        # Grab user from subjects
        users_query = {"_id": {"$in": [sub["teacher_id"] for sub in subjects]}}
        users = self.user_coll.find(users_query, {"username": 1})
        users_map = dict((x["_id"], x["username"]) for x in users)

        # generate names
        sub_names = [
            f"{sub['subject']} - {sub['course']} - {users_map.get(sub['teacher_id'])}"
            for sub in subjects
        ]
        return ", ".join(sub_names)

    def message_formatter(self, content, model, name):
        # http://192.168.1.156:1337/admin/informationview/details/?id=
        info_detail_base_url = f"{request.host_url}admin/informationview/details/?id="
        value: str = "<div>"
        for item in model[name]:
            info_query = {
                "_id": {"$in": [ObjectId(src_id) for src_id in item["source_ids"]]}
            }
            info_cursor = self.info_coll.find(info_query, {"headline": 1})
            source_ids = [
                f'<a href="{info_detail_base_url}{str(info["_id"])}">{info["headline"]}</a>'
                for info in info_cursor
            ]
            ids = ", ".join(source_ids)

            message = f"""<table class="table" border="1" bordercolor="#ddd">
                <tr><td><b>Message</b></td>
                <td>{item['message']}</td></tr>
                <tr><td><b>Response</b></td>
                <td>{item['response']}</td></tr>
                <tr><td><b>Tag</b></td>
                <td>{item['tag']}</td></tr>
                <tr><td><b>Source_ids</b></td>
                <td>{ids}</td></tr></table>"""
            value += message

        value += "</div>"
        return Markup(value)

    column_formatters = {
        "date": date_formatter,
        "subjects": subjects_formatter,
        "messages": message_formatter,
    }

    page_size = 10_000
    can_view_details = True
    can_create = False
    can_edit = False

    details_template = "custom_details.html"

    form = Chat_HistoryForm

    def __init__(self, info_coll, sub_coll, user_coll, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.info_coll = info_coll
        self.sub_coll = sub_coll
        self.user_coll = user_coll

    def get_list(self, *args, **kwargs):
        count, data = super(Chat_HistoryView, self).get_list(*args, **kwargs)

        if not login.current_user.is_admin:
            new_data = []
            user_id = ObjectId(login.current_user.id)

            for chat_history in data:
                # Get Subjects
                sub_query = {"_id": {"$in": chat_history["subjects"]}}
                sub_cursor = self.sub_coll.find(sub_query, {"teacher_id": 1})
                subjects = [item["teacher_id"] for item in sub_cursor]
                if user_id in subjects:
                    new_data.append(chat_history)

            data = new_data
            count = len(data)

        return count, data

    def is_accessible(self):
        return login.current_user.is_authenticated and super().is_accessible()

    def is_action_allowed(self, name):
        self.can_delete = login.current_user.is_admin
        return super(Chat_HistoryView, self).is_action_allowed(name)


class ExceptionForm(form.Form):
    endpoint = fields.StringField("Endpoint")
    time = fields.DateTimeField("Time")
    exception = fields.TextAreaField("Exception")


class ExceptionView(ModelView):
    column_list = ("endpoint", "time")
    column_sortable_list = ("endpoint", "time")

    column_filters = (
        filters.FilterLike("endpoint", "Endpoint"),
        filters.FilterNotLike("endpoint", "Endpoint"),
    )

    column_details_list = ("endpoint", "time", "exception")

    page_size = 10_000
    can_view_details = True
    can_create = False
    can_edit = False

    form = ExceptionForm

    def is_accessible(self):
        return (
            login.current_user.is_authenticated
            and login.current_user.is_admin
            and super().is_accessible()
        )


class InformationForm(form.Form):
    headline = fields.StringField("Headline", validators=[validators.InputRequired()])
    content = fields.TextAreaField("Content", validators=[validators.InputRequired()])
    source = fields.StringField("Source", validators=[validators.InputRequired()])
    subject_id = fields.SelectField("Subject", widget=Select2Widget())
    tag = fields.StringField("Tag", render_kw={"readonly": True})
    mark_for_delete = fields.BooleanField("Mark for Delete")


class InformationView(ModelView):
    column_list = ("headline", "subject", "tag", "mark_for_delete")
    column_sortable_list = ("tag",)

    column_filters = (
        filters.FilterEqual("tag", "Tag"),
        filters.FilterNotEqual("tag", "Tag"),
        filters.BooleanEqualFilter("mark_for_delete", "Mark for Delete"),
        filters.BooleanNotEqualFilter("mark_for_delete", "Mark for Delete"),
    )

    column_details_list = (
        "headline",
        "subject",
        "tag",
        "mark_for_delete",
        "source",
        "content",
    )

    def subject_formatter(self, content, model, name):
        if not name in model:
            # Get subject
            subject = self.sub_coll.find_one({"_id": model["subject_id"]})
            # Get user from subject
            user = self.user_coll.find_one(
                {"_id": subject["teacher_id"]}, {"username": 1}
            )
            return f"{subject['subject']} - {subject['course']} - {user['username']}"
        else:
            return model[name]

    column_formatters = {"subject": subject_formatter}

    page_size = 10_000
    can_view_details = True
    can_delete = False
    can_create = True

    list_template = "info_list.html"
    details_template = "custom_details.html"

    form = InformationForm

    def __init__(self, sub_coll, user_coll, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sub_coll = sub_coll
        self.user_coll = user_coll

    def get_list(self, *args, **kwargs):
        count, data = super(InformationView, self).get_list(*args, **kwargs)

        # Grab subjects
        if login.current_user.is_admin:
            sub_query = {"_id": {"$in": [x["subject_id"] for x in data]}}
        else:
            sub_query = {
                "$and": [
                    {"_id": {"$in": [x["subject_id"] for x in data]}},
                    {"teacher_id": ObjectId(login.current_user.id)},
                ]
            }

        sub_cursor = self.sub_coll.find(sub_query)
        subjects = [x for x in sub_cursor]

        # Grab user from subjects
        query = {"_id": {"$in": [x["teacher_id"] for x in subjects]}}
        users = self.user_coll.find(query, {"username": 1})
        users_map = dict((x["_id"], x["username"]) for x in users)

        subjects_map = dict(
            (
                x["_id"],
                f"{x['subject']} - {x['course']} - {users_map.get(x['teacher_id'])}",
            )
            for x in subjects
        )

        new_data = []
        for item in data:
            if item["subject_id"] in subjects_map:
                item["subject"] = subjects_map.get(item["subject_id"])
            else:
                item["subject"] = ""

            if login.current_user.is_admin or item["subject"] != "":
                new_data.append(item)

        data = new_data
        count = len(data)

        return count, data

    # Contribute list of user choices to the forms
    def _feed_subject_choices(self, form):
        if login.current_user.is_admin:
            sub_query = {}
        else:
            sub_query = {"teacher_id": ObjectId(login.current_user.id)}

        query_result = self.sub_coll.find(sub_query)
        subjects = [x for x in query_result]

        users_query = {"_id": {"$in": [x["teacher_id"] for x in subjects]}}
        users = self.user_coll.find(users_query, {"username": 1})
        users_map = dict((x["_id"], x["username"]) for x in users)

        form.subject_id.choices = [
            (
                str(x["_id"]),
                f"{x['subject']} - {x['course']} - {users_map.get(x['teacher_id'])}",
            )
            for x in subjects
        ]

        return form

    def render(self, template, **kwargs):
        kwargs.update({"cref_token": self.admin.app.config["CREF_TOKEN"]})
        return super().render(template, **kwargs)

    def create_form(self):
        form = super(InformationView, self).create_form()
        form["tag"].data = MongoDBConnection.ADD_INFO_TAG
        del form["mark_for_delete"]
        return self._feed_subject_choices(form)

    def edit_form(self, obj):
        form = super(InformationView, self).edit_form(obj)
        form["tag"].data = MongoDBConnection.EDIT_INFO_TAG
        return self._feed_subject_choices(form)

    def on_model_change(self, form, model, is_created):
        subject_id = model.get("subject_id")
        model["subject_id"] = ObjectId(subject_id)

        return model

    def is_accessible(self):
        return login.current_user.is_authenticated and super().is_accessible()

    @action(
        "set_live",
        "Set Live",
        "Are you sure you want to set selected informations live?",
    )
    def action_set_live(self, ids):
        try:
            mongodb_lock.acquire(blocking=True)

            query = {"_id": {"$in": [ObjectId(id) for id in ids]}}
            MongoDBConnection.update_information_tag(
                query, MongoDBConnection.PRE_LIVE_INFO_TAG
            )

            msg = f"Successfully set '{len(ids)}' information items live."
            write_log(msg)
            flash(msg)

            mongodb_lock.release()
        except Exception as ex:
            if not self.handle_view_exception(ex):
                raise

            flash(f"Failed to set information live: '{str(ex)}'", "error")

    @action(
        "remove",
        "Remove",
        "Are you sure you want to remove selected informations?",
    )
    def action_remove(self, ids):
        try:
            mongodb_lock.acquire(blocking=True)

            for id in ids:
                MongoDBConnection.delete_information(id)

            msg = f"Successfully removed '{len(ids)}' information items."
            write_log(msg)
            flash(msg)

            mongodb_lock.release()
        except Exception as ex:
            if not self.handle_view_exception(ex):
                raise

            flash(f"Failed to set information live: '{str(ex)}'", "error")

    def is_action_allowed(self, name):
        # Check remove/set_live action permission
        if (name == "remove" or name == "set_live") and not login.current_user.is_admin:
            return False

        return super(InformationView, self).is_action_allowed(name)

    @expose("/")
    def index(self):
        if hasattr(login.current_user, "is_admin"):
            self._template_args["has_admin_authorization"] = login.current_user.is_admin
        return self.index_view()


class OpenAI_KeyForm(form.Form):
    api_key = fields.StringField("API Key", validators=[validators.InputRequired()])


class OpenAI_KeyView(ModelView):
    column_list = ("api_key",)

    can_create = False

    form = OpenAI_KeyForm

    def is_accessible(self):
        return (
            login.current_user.is_authenticated
            and login.current_user.is_admin
            and super().is_accessible()
        )


class SubjectForm(form.Form):
    course = fields.StringField("Course", validators=[validators.InputRequired()])
    subject = fields.StringField("Subject", validators=[validators.InputRequired()])
    teacher_id = fields.StringField("Teacher", render_kw={"readonly": True})


class SubjectAdminForm(form.Form):
    course = fields.StringField("Course", validators=[validators.InputRequired()])
    subject = fields.StringField("Subject", validators=[validators.InputRequired()])
    teacher_id = fields.SelectField("Teacher", widget=Select2Widget())


class SubjectView(ModelView):
    column_list = ("course", "subject", "teacher")
    column_sortable_list = ("subject",)

    column_filters = (
        filters.FilterEqual("course", "Course"),
        filters.FilterNotEqual("course", "Course"),
        filters.FilterLike("subject", "Subject"),
        filters.FilterNotLike("subject", "Subject"),
    )

    page_size = 10_000

    form = SubjectForm

    def __init__(self, user_coll, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_coll = user_coll

    def get_list(self, *args, **kwargs):
        count, data = super(SubjectView, self).get_list(*args, **kwargs)

        if login.current_user.is_admin:
            # Grab user names
            query = {"_id": {"$in": [x["teacher_id"] for x in data]}}
            users = self.user_coll.find(query, {"username": 1})

            # Contribute user names to the models
            users_map = dict((x["_id"], x["username"]) for x in users)
        else:
            users_map = {ObjectId(login.current_user.id): login.current_user.username}

        new_data = []
        for item in data:
            if item["teacher_id"] in users_map:
                item["teacher"] = users_map.get(item["teacher_id"])
                new_data.append(item)

        data = new_data
        count = len(data)

        return count, data

    # Contribute list of user choices to the forms
    def _feed_user_choices(self, form):
        users = self.user_coll.find({}, {"username": 1})
        form.teacher_id.choices = [
            (str(user["_id"]), user["username"]) for user in users
        ]
        return form

    def create_form(self):
        if login.current_user.is_admin:
            if self.form is not SubjectAdminForm:
                self.form = SubjectAdminForm
                self._refresh_forms_cache()

            form = super(SubjectView, self).create_form()
            return self._feed_user_choices(form)
        else:
            if self.form is not SubjectForm:
                self.form = SubjectForm
                self._refresh_forms_cache()

            form = super(SubjectView, self).create_form()
            form["teacher_id"].data = login.current_user.username
            return form

    def edit_form(self, obj):
        if login.current_user.is_admin:
            if self.form is not SubjectAdminForm:
                self.form = SubjectAdminForm
                self._refresh_forms_cache()

            form = super(SubjectView, self).edit_form(obj)
            return self._feed_user_choices(form)
        else:
            if self.form is not SubjectForm:
                self.form = SubjectForm
                self._refresh_forms_cache()

            form = super(SubjectView, self).edit_form(obj)
            form["teacher_id"].data = login.current_user.username
            return form

    # Correct user_id reference before saving
    def on_model_change(self, form, model, is_created):
        if login.current_user.is_admin:
            teacher_id = model.get("teacher_id")
        else:
            teacher_id = login.current_user.id

        model["teacher_id"] = ObjectId(teacher_id)

        return model

    def is_accessible(self):
        return login.current_user.is_authenticated and super().is_accessible()


class UserForm(form.Form):
    username = fields.StringField("Username", validators=[validators.InputRequired()])
    password = fields.StringField("Password", validators=[validators.InputRequired()])
    is_admin = fields.BooleanField("Is Admin")


class UserView(ModelView):
    column_list = ("username", "password", "is_admin")
    column_sortable_list = ("username", "password", "is_admin")

    column_filters = (
        filters.FilterLike("username", "Username"),
        filters.FilterNotLike("username", "Username"),
    )

    form = UserForm

    def is_accessible(self):
        return (
            login.current_user.is_authenticated
            and login.current_user.is_admin
            and super().is_accessible()
        )
