from bson.datetime_ms import DatetimeMS
from bson.objectid import ObjectId
from datetime import datetime, timedelta
from pymongo import MongoClient
from typing import List


# NOTE: We need to convert our Data Containers to a dict to convert them to BSON format
def to_dict(obj):
    return vars(obj)


# NOTE: Basically whats happening :
# return {
#     "var_1":self.var_1,
#     "var_2":self.var_2,
#     ...
#     "var_n": self.var_n,
# }


class ChatMessage:
    def __init__(self, message: str, response: str, tag: str, source_ids: List[str]):
        self.message = message
        self.response = response
        self.tag = tag
        self.source_ids = source_ids


class ChatHistory:
    def __init__(
        self,
        start_message: str,
        description: str,
        date: str,
        subjects: List[ObjectId],
        messages: List[ChatMessage],
    ):
        self.start_message = start_message
        self.description = description
        self.date = date
        self.subjects = subjects
        if messages == None:
            self.messages = []
        else:
            self.messages = messages


class Information:
    def __init__(
        self,
        headline: str,
        content: str,
        source: str,
        subject: str,
        tag: str,
        delete_message: str,
    ):
        self.headline = headline
        self.content = content
        self.source = source
        self.subject = subject
        self.tag = tag
        self.delete_message = delete_message


class Exception:
    def __init__(self, endpoint: str, time: str, exception: str):
        self.endpoint = endpoint
        self.time = time
        self.exception = exception


class MongoDBConnection:
    CONNECTION: str = "mongodb:27017"
    # CONNECTION: str = "mongodb://localhost:27017"
    DATABASE: str = "Chatbot"

    CHAT_HISTORY_COLL: str = "Chat_History"
    EXCEPTION_COLL: str = "Exception"
    INFORMATION_COLL: str = "Information"
    OPENAI_COLL: str = "OpenAI"
    SUBJECT_COLL: str = "Subject"
    USER_COLL: str = "User"
    BEARER_COLL: str = "Bearer_Token"

    REVIEWED_MSG_TAG: str = "reviewed"
    NEUTRAL_MSG_TAG: str = "neutral"
    MARK_FOR_REVIEW_MSG_TAG: str = "marked for review"

    LIVE_INFO_TAG: str = "Current-Live"
    PRE_LIVE_INFO_TAG: str = "Pending-Live"
    ADD_INFO_TAG: str = "New-Entry"
    EDIT_INFO_TAG: str = "Modified"

    DEFAULT: str = "Default"

    EXPIRATION_TIME: timedelta = timedelta(hours=4)

    # ----- DB Operations ------------------------------------------------------------------------------------------------
    # ! If you are working with this class: call this function befor everything else !
    @classmethod
    def connect_to_database(cls):
        cls.client = MongoClient(cls.CONNECTION)
        cls.db = cls.client[cls.DATABASE]
        cls.connect_to_chat_history()
        cls.connect_to_exception()
        cls.connect_to_information()
        cls.connect_to_openai()
        cls.connect_to_subject()
        cls.connect_to_user()
        cls.connect_to_bearer_token()
        return cls.db

    @classmethod
    def connect_to_chat_history(cls):
        cls.chat_history = cls.db[cls.CHAT_HISTORY_COLL]
        return cls.chat_history

    @classmethod
    def connect_to_exception(cls):
        cls.exception = cls.db[cls.EXCEPTION_COLL]
        return cls.exception

    @classmethod
    def connect_to_information(cls):
        cls.information = cls.db[cls.INFORMATION_COLL]
        return cls.information

    @classmethod
    def connect_to_openai(cls):
        cls.openai = cls.db[cls.OPENAI_COLL]
        return cls.openai

    @classmethod
    def connect_to_subject(cls):
        cls.subject = cls.db[cls.SUBJECT_COLL]
        return cls.subject

    @classmethod
    def connect_to_user(cls):
        cls.user = cls.db[cls.USER_COLL]
        return cls.user

    @classmethod
    def connect_to_bearer_token(cls):
        cls.bearer_token = cls.db[cls.BEARER_COLL]
        return cls.bearer_token

    # ----- API access Chat History --------------------------------------------------------------------------------------
    @classmethod
    def create_chat_history(cls, start_message: str):
        time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        date = DatetimeMS(time)
        history = ChatHistory(start_message, cls.DEFAULT, date, [], [])
        result = cls.chat_history.insert_one(to_dict(history))
        return result.inserted_id

    @classmethod
    def get_last_messages(cls, id: str, amount: int):
        history = cls.chat_history.find_one({"_id": ObjectId(id)})
        messages = history["messages"]
        message_amount = 0
        if messages != None:
            message_amount = len(messages)
        amount = min(amount, message_amount)
        last_messages = []
        for i in range(amount - 1, -1, -1):
            last_messages.append(history["messages"][message_amount - 1 - i])
        return last_messages

    @classmethod
    def add_chat_history_message(
        cls, id: str, message: str, response: str, tag: str, source_ids: List[str]
    ):
        message = ChatMessage(message, response, tag, source_ids)
        return cls.chat_history.update_one(
            {"_id": ObjectId(id)},
            {"$addToSet": {"messages": to_dict(message)}},
        )

    @classmethod
    def get_chat_history(cls, history_id: str):
        result = cls.chat_history.find_one({"_id": ObjectId(history_id)})
        for key in ["_id", "description", "date", "subjects"]:
            del result[key]
        result["messages"] = [
            {"message": msg["message"], "response": msg["response"]}
            for msg in result["messages"]
        ]
        return result

    @classmethod
    def update_chat_history(
        cls,
        id: str,
        description: str | None,
        subjects_to_add: List[ObjectId],
        response: str,
        source_ids: List[str],
    ):
        obj_id = ObjectId(id)
        chat_history = cls.chat_history.find_one({"_id": obj_id})

        current_subjects = chat_history["subjects"]
        current_subjects.extend(
            subject for subject in subjects_to_add if subject not in current_subjects
        )

        msg_size = len(chat_history["messages"]) - 1

        update = {
            "$set": {
                "subjects": current_subjects,
                f"messages.{msg_size}.response": response,
                f"messages.{msg_size}.source_ids": source_ids,
            }
        }

        if description is not None:
            update["$set"]["description"] = description

        return cls.chat_history.update_one(
            {"_id": obj_id},
            update,
        )

    @classmethod
    def set_message_tag(cls, history_id: str, message_idx: int, tag: str):
        return cls.chat_history.update_one(
            {"_id": ObjectId(history_id)},
            {"$set": {f"messages.{message_idx}.tag": tag}},
        )

    # ----- API access Information ---------------------------------------------------------------------------------------
    @classmethod
    def get_information_subject_ids(cls, info_ids: List[str]):
        query = {"_id": {"$in": [ObjectId(id) for id in info_ids]}}
        info_cursor = cls.information.find(query, {"_id": 0, "subject_id": 1})
        return [info["subject_id"] for info in info_cursor]

    @classmethod
    def get_live_information(cls):
        cursor = cls.information.find(
            {
                "tag": {
                    "$in": [
                        MongoDBConnection.LIVE_INFO_TAG,
                        MongoDBConnection.PRE_LIVE_INFO_TAG,
                    ]
                }
            }
        )
        information = [dict(document, _id=str(document["_id"])) for document in cursor]
        return information

    @classmethod
    def delete_information(cls, id: str):
        result = cls.information.delete_one({"_id": ObjectId(id)})
        return result.deleted_count == 1

    @classmethod
    def update_information_tag(cls, query: str, tag: str):
        result = cls.information.update_many(query, {"$set": {"tag": tag}})
        return result.modified_count

    @classmethod
    # def add_exception(cls, name: str, time: datetime, exception: str):
    def add_exception(cls, name: str, exception: str):
        time = datetime.now()
        date = DatetimeMS(time)
        result = cls.exception.insert_one(to_dict(Exception(name, date, exception)))
        return result

    @classmethod
    def get_bearer_token(cls):
        expiration_date = datetime.now().replace(microsecond=0) + cls.EXPIRATION_TIME
        result = cls.bearer_token.insert_one(
            {"expiration_date": DatetimeMS(expiration_date)}
        )
        token = {
            "token": str(result.inserted_id),
            "expiration_date": str(expiration_date),
        }
        return token

    @classmethod
    def verify_bearer_token(cls, token_id: str):
        try:
            expiration_date = datetime.now().replace(microsecond=0)
            cls.bearer_token.delete_many(
                {"expiration_date": {"$lt": DatetimeMS(expiration_date)}}
            )
            result = cls.bearer_token.find_one({"_id": ObjectId(token_id)})
            return result != None

        except:
            return False
