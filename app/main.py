from langchain.memory import ConversationBufferWindowMemory
from bson.objectid import ObjectId
from flask_admin import Admin, AdminIndexView, helpers, expose
from flask_cors import CORS
from wtforms import form, fields, validators
from typing import Callable
from flask import Flask, Response, url_for, redirect, stream_with_context, request
from queue import Queue

from .langchain_connection import LangChainConnection
from .mongodb_connection import MongoDBConnection
from .streaming_handler import StreamingHandler
from . import admin_classes as ad_cls

import flask_login as login

import traceback
import threading
import json
import os

INSTRUCT_MODEL: str = "gpt-3.5-turbo"  # NOTE: Limitiert auf 4096 Tokens!
CHAT_MODEL: str = "gpt-3.5-turbo"
MEMORY_SIZE: int = 4

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
app.config["API-KEY"] = os.environ.get("API_KEY")
app.config["CREF_TOKEN"] = os.environ.get("CREF_TOKEN")
app.config["OPEN_AI_UID"] = os.environ.get("OPEN_AI_UID")
app.config["MASTER_ID"] = os.environ.get("MASTER_ID")
app.config["MASTER_NAME"] = os.environ.get("MASTER_NAME")
app.config["MASTER_PASS"] = os.environ.get("MASTER_PASS")
cors = CORS(app)


def verify_bearer_token():
    token = request.headers.get("BEARER-TOKEN", None)
    valid = MongoDBConnection.verify_bearer_token(token)
    return valid


def verify_header_in_config(key: str):
    value = request.headers.get(key, None)
    value_config = app.config.get(key, None)
    return value == value_config


def exception_wrapper(function: Callable[..., Response], *args, **kwargs) -> Response:
    try:
        return function(*args, **kwargs)
    except Exception as ex:
        error = traceback.format_exc()
        MongoDBConnection.add_exception(function.__name__, error)
        print(error, flush=True)
        return Response(str(ex), 500, mimetype="text/plain")


def request_not_acceptable(function: Callable) -> Response:
    return Response(
        response=f"Server endpoint '/{function.__name__}' expects a content-type of type: 'application/json'",
        status=406,
        mimetype="text/plain",
    )


# ============================================= Admin Login ===================================================
# Define login and registration forms (for flask-login)
class LoginForm(form.Form):
    login = fields.StringField(validators=[validators.InputRequired()])
    password = fields.PasswordField(validators=[validators.InputRequired()])

    def validate_login(self, field):
        user = self.get_user()

        if user is None:
            raise validators.ValidationError("Invalid user")

        if user.username == app.config["MASTER_NAME"]:
            if user.password == app.config["MASTER_PASS"]:
                return
            else:
                raise validators.ValidationError("Invalid password")

        if user.password != self.password.data:
            raise validators.ValidationError("Invalid password")

    def get_user(self) -> ad_cls.User:
        if self.login.data == app.config["MASTER_NAME"]:
            return ad_cls.User(
                {
                    "_id": app.config["MASTER_ID"],
                    "username": self.login.data,
                    "password": self.password.data,
                    "is_admin": True,
                }
            )
        else:
            result = MongoDBConnection.db.User.find_one({"username": self.login.data})
            if result:
                return ad_cls.User(result)
            return None


# Initialize flask-login
def init_login():
    login_manager = login.LoginManager()
    login_manager.init_app(app)

    # Create user loader function
    @login_manager.user_loader
    def load_user(user_id):
        if user_id == app.config["MASTER_ID"]:
            return ad_cls.User(
                {
                    "_id": app.config["MASTER_ID"],
                    "username": app.config["MASTER_NAME"],
                    "password": app.config["MASTER_PASS"],
                    "is_admin": True,
                }
            )
        else:
            result = MongoDBConnection.db.User.find_one({"_id": ObjectId(user_id)})
            if result:
                return ad_cls.User(result)
            return None


# Create customized index view class that handles login & registration
class MyAdminIndexView(AdminIndexView):
    def add_log(self):
        pass
        # path = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
        # text = None
        # with open(os.path.join(path, "log.txt"), "r", encoding="utf-8") as file:
        #     text = file.read()
        #     file.close()
        #
        # if text is not None:
        #     self._template_args["log"] = text

    def add_admin_info(self):
        if hasattr(login.current_user, "is_admin"):
            self._template_args["has_admin_authorization"] = login.current_user.is_admin

    @expose("/")
    def index(self):
        if not login.current_user.is_authenticated:
            return redirect(url_for(".login_view"))
        self.add_log()
        self.add_admin_info()
        return super(MyAdminIndexView, self).index()

    @expose("/login/", methods=("GET", "POST"))
    def login_view(self):
        # handle user login
        form = LoginForm(request.form)
        if helpers.validate_form_on_submit(form):
            user = form.get_user()
            login.login_user(user)

        if login.current_user.is_authenticated:
            return redirect(url_for(".index"))

        self._template_args["form"] = form
        self.add_log()
        self.add_admin_info()
        return super(MyAdminIndexView, self).index()

    @expose("/logout/")
    def logout_view(self):
        login.logout_user()
        return redirect(url_for(".index"))


# ============================================= Student Endpoints =============================================
@app.route("/")
def index():
    return "Hello World!"


@app.route("/get_token", methods=["GET"])
@app.route("/get_token/", methods=["GET"])
def get_token():
    def _get_token():
        # Check API_KEY
        if verify_header_in_config("API-KEY") == False:
            return Response(status=401)

        token = MongoDBConnection.get_bearer_token()
        response = json.dumps(token, default=lambda o: o.__dict__)
        return Response(response, 200, mimetype="application/json")

    return exception_wrapper(_get_token)


# Starts a new Chat-Session, where a ChatHistory is created and the student is greeted by the API as Hugo Eckener
# OR
# Return the complete data for a specific chat history
# JsonData: {"history_id":"649d455a00e6409df6ee9f92"}
@app.route("/start_session", methods=["POST", "GET"])
@app.route("/start_session/", methods=["POST", "GET"])
def start_session():
    if verify_bearer_token() == False:
        return Response(status=401)

    # Generate greeting msg
    def _start_session():
        result = LangChainConnection.generate_simple_completion(
            INSTRUCT_MODEL, LangChainConnection.START_CHAT_MSG
        )

        history_id = MongoDBConnection.create_chat_history(result)
        data = {"history_id": str(history_id), "message": result}
        response = json.dumps(data, default=lambda o: o.__dict__)
        return Response(response, 200, mimetype="application/json")

    # Get chat history
    def _get_history_data(data: dict):
        if "history_id" in data:
            result = MongoDBConnection.get_chat_history(data["history_id"])
            response = json.dumps(result, default=lambda o: o.__dict__)
            return Response(response, 200, mimetype="application/json")
        else:
            raise KeyError(
                f"Data should contain 'history_id' but didn't. Received: {data.keys()}"
            )

    if request.is_json:
        json_data = request.json
        return exception_wrapper(_get_history_data, json_data)
    else:
        return exception_wrapper(_start_session)


# !IMORTANT: If you call this from inside your browser do NOT use "?". Insteat use the URL encoded version "%3F"!
# Calls the API via Langchain(ConversationalRetrievalChain) and returns the output as Token-Stream
# JsonData: {"history_id":"649d455a00e6409df6ee9f92", "message":"Is this a sample question %3F"}
@app.route("/get_response", methods=["POST", "GET"])
@app.route("/get_response/", methods=["POST", "GET"])
def get_response():
    def _get_response(data: dict) -> Response:
        if verify_bearer_token() == False:
            return Response(status=401)

        queue = Queue()
        callback_fn = StreamingHandler(queue)

        def generate_token_stream(token_queue: Queue):
            is_reading_tokens = True
            while is_reading_tokens:
                token = token_queue.get()
                if token == StreamingHandler.STOP_ITEM:
                    is_reading_tokens = False
                else:
                    yield token

        def get_api_response(
                data_history_id: str, data_message: str, callback_fn: StreamingHandler
        ):
            try:
                last_messages = MongoDBConnection.get_last_messages(
                    data_history_id, MEMORY_SIZE
                )

                MongoDBConnection.add_chat_history_message(
                    data_history_id,
                    data_message,
                    "",
                    MongoDBConnection.NEUTRAL_MSG_TAG,
                    [],
                )

                memory = ConversationBufferWindowMemory(
                    k=MEMORY_SIZE,
                    memory_key="chat_history",
                    output_key="answer",
                    return_messages=True,
                )
                for msg in last_messages:
                    memory.chat_memory.add_user_message(msg["message"])
                    memory.chat_memory.add_ai_message(msg["response"])
                result = LangChainConnection.generate_qa_completion(
                    CHAT_MODEL, memory, callback_fn, data_message
                )

                source_ids = [
                    str(sources.metadata["source"])
                    for sources in result["source_documents"]
                ]

                description = None
                if len(last_messages) == 0:
                    description = LangChainConnection.generate_simple_completion(
                        INSTRUCT_MODEL,
                        LangChainConnection.DESCRIPTION_INSTRUCTION,
                        {"message": data_message, "result": result["answer"]},
                    )

                subject_ids = MongoDBConnection.get_information_subject_ids(source_ids)

                MongoDBConnection.update_chat_history(
                    data_history_id,
                    description,
                    subject_ids,
                    result["answer"],
                    source_ids,
                )

            except Exception as ex:
                callback_fn.queue.put(str(ex))
                callback_fn.queue.put(StreamingHandler.STOP_ITEM)

        if "history_id" in data and "message" in data:
            thread = threading.Thread(
                target=get_api_response,
                args=(data["history_id"], data["message"], callback_fn),
            )
            thread.start()
        else:
            raise KeyError(
                f"Data should contain 'history_id' and 'message' but didn't. Received: {data.keys()}"
            )

        return Response(stream_with_context(generate_token_stream(queue)), 200)

    if request.is_json:
        json_data = request.json
        return exception_wrapper(_get_response, json_data)
    else:
        return request_not_acceptable(get_response)


# Tag an chat message for review. Should only be called by student frontend.
# JsonData: {"history_id":"649d455a00e6409df6ee9f92", "message_idx":0}
@app.route("/tag_message_for_review", methods=["POST"])
@app.route("/tag_message_for_review/", methods=["POST"])
def tag_message_for_review():
    def _tag_message_for_review(data: dict):
        if verify_bearer_token() == False:
            return Response(status=401)

        if "history_id" in data and "message_idx" in data:
            MongoDBConnection.set_message_tag(
                data["history_id"],
                data["message_idx"],
                MongoDBConnection.MARK_FOR_REVIEW_MSG_TAG,
            )
            return Response(status=200)
        else:
            raise KeyError(
                f"Data should contain 'history_id' and 'message_idx' but didn't. Received: {data.keys()}"
            )

    if request.is_json:
        json_data = request.json
        return exception_wrapper(_tag_message_for_review, json_data)
    else:
        return request_not_acceptable(tag_message_for_review)


# ============================================= Teacher Endpoints =============================================
# Generates a headline given a chunk of information.
# A headline is necessary for better results of similarity search with Weviate
# JsonData: {"context":"Any context"}
@app.route("/generate_headline", methods=["POST", "GET"])
@app.route("/generate_headline/", methods=["POST", "GET"])
def generate_headline():
    def _generate_headline(data: dict):
        if verify_bearer_token() == False:
            return Response(status=401)

        if "content" in data:
            result = LangChainConnection.generate_simple_completion(
                INSTRUCT_MODEL,
                LangChainConnection.HEADLINE_INSTRUCTION,
                {"content": data["content"]},
            )
            return Response(result, 200, mimetype="text/plain")
        else:
            raise KeyError(
                f"Data should contain 'content' but didn't. Received: {data.keys()}"
            )

    if request.is_json:
        json_data = request.json
        return exception_wrapper(_generate_headline, json_data)
    else:
        return request_not_acceptable(generate_headline)


# ============================================= Admin Endpoints =============================================
weaviate_lock = threading.Lock()


# Updates the vector-store with the current informations in the database
@app.route("/update_vector_store", methods=["POST", "GET"])
@app.route("/update_vector_store/", methods=["POST", "GET"])
def update_vector_store():
    # Check CREF_TOKEN
    if verify_header_in_config("CREF_TOKEN") == False:
        return Response(status=401)

    ad_cls.mongodb_lock.acquire(blocking=True)

    if weaviate_lock.acquire(blocking=False):
        try:
            weaviate = LangChainConnection.create_weaviate()
            if weaviate is not None:
                query = {"tag": MongoDBConnection.PRE_LIVE_INFO_TAG}
                MongoDBConnection.update_information_tag(
                    query, MongoDBConnection.LIVE_INFO_TAG
                )
                type = "info"
                msg = "Successfully updated weaviate vector store."
            else:
                type = "warning"
                msg = "Something went wrong during the weaviate vector store update. Please try again later."
        except Exception as ex:
            type = "error"
            msg = f"Failed to update weaviate vector store: '{str(ex)}'"

        weaviate_lock.release()
    else:
        type = "warning"
        msg = "Weaviate vector store update allready in progress."

    # Update admin log
    ad_cls.write_log(msg)

    ad_cls.mongodb_lock.release()

    data = {"type": type, "msg": msg}
    return Response(
        json.dumps(data),
        status=200,
        mimetype="application/json",
    )


# ============================================= Runtime =====================================================
# Initialize flask-login
init_login()

# Setup mongodb connection
MongoDBConnection.connect_to_database()

# Setup langchain connection
LangChainConnection.setup_langchain(app.config["OPEN_AI_UID"])

# Create admin
admin = Admin(
    app,
    "Chatbot Admin",
    index_view=MyAdminIndexView(),
    base_template="master_w_login.html",
    template_mode="bootstrap4",
)

admin.add_view(
    ad_cls.Chat_HistoryView(
        MongoDBConnection.information,
        MongoDBConnection.subject,
        MongoDBConnection.user,
        MongoDBConnection.chat_history,
        "Chat History",
    )
)
admin.add_view(
    ad_cls.ExceptionView(
        MongoDBConnection.exception,
        "Exception",
    )
)
admin.add_view(
    ad_cls.InformationView(
        MongoDBConnection.subject,
        MongoDBConnection.user,
        MongoDBConnection.information,
        name="Information",
    )
)
admin.add_view(
    ad_cls.OpenAI_KeyView(
        MongoDBConnection.openai,
        "OpenAI",
    )
)
admin.add_view(
    ad_cls.SubjectView(
        MongoDBConnection.user,
        MongoDBConnection.subject,
        name="Subject",
    )
)
admin.add_view(
    ad_cls.UserView(
        MongoDBConnection.user,
        "User",
    )
)

# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port="1337", debug=True, ssl_context="adhoc")
