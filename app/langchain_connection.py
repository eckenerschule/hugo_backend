import weaviate
from langchain.vectorstores.weaviate import Weaviate
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.chat_models import ChatOpenAI

from langchain.memory import ConversationBufferWindowMemory
from langchain.chains import LLMChain
from langchain import PromptTemplate
from typing import Dict, Any

from .streaming_handler import StreamingHandler
from .mongodb_connection import MongoDBConnection
from .conversationalRetrievalChain import ConversationalRetrievalChain


class LangChainConnection:
    URL: str = "http://weaviate:8080/"
    # URL: str = "http://localhost:8080/"
    INDEX_NAME: str = "Information_Vectorstore"

    START_CHAT_MSG: str = """Du heißt Hugo Eckener und bist ein Luftschiffführer der sehr gerne anderen bei ihren Problemen hilft. 
    Begrüße einen Schüler und stelle dich vor. 
    Dutze deinen gegenüber immer. 
    Du darfst Emoticons benutzen. 
    Stelle bei der Begrüßung keine Fragen."""

    DESCRIPTION_INSTRUCTION = """Fasse folgende Konversation in weniger als 5 Worten zusammen. Benutze dabei keine Anführungszeichen '"'.
    Konversation:
    Frage: {message}
    Antwort: {result}"""

    HEADLINE_INSTRUCTION = """Erstelle einen Titel für den folgenden Text. Benutze dabei keine Anführungszeichen '"'.
    Tex: {content}"""

    @classmethod
    def setup_langchain(cls, openai_uid: str):
        cls.openai_uid = openai_uid
        result = MongoDBConnection.openai.find_one({"uid": cls.openai_uid})
        if result is None:
            MongoDBConnection.openai.insert_one(
                {
                    "uid": cls.openai_uid,
                    "api_key": "Please add your openai api key and update the weaviate vector store befor activating the chat bot.",
                }
            )

    @classmethod
    def get_openai_api_key(cls) -> str:
        if cls.openai_uid:
            result = MongoDBConnection.openai.find_one({"uid": cls.openai_uid})
            openai_key = result["api_key"]
            if openai_key:
                return openai_key
            else:
                raise Exception(
                    "Missing OpenAI API Key. Please contact your admin or add the api key."
                )
        else:
            raise Exception(
                "Missing OpenAI UID. Please provide a openai uid and restart the server."
            )

    @classmethod
    def get_qa_chain(
            cls,
            model: str,
            memory: ConversationBufferWindowMemory,
            callbackStream: StreamingHandler,
    ) -> ConversationalRetrievalChain:
        openai_key = cls.get_openai_api_key()

        client = weaviate.Client(
            url=cls.URL,
            additional_headers={"X-OpenAI-Api-Key": openai_key},
        )
        embedding = OpenAIEmbeddings(openai_api_key=openai_key)
        vector_store = Weaviate(
            client=client,
            index_name=cls.INDEX_NAME,
            text_key="text",
            embedding=embedding,
            attributes=["source"],
        )

        template = """Du heißt Hugo Eckener und ein freundlicher älterer Herr der sehr gerne anderen bei ihren Problemen hilft. Dutze deinen gegenüber immer.
        
        Falls die Antwort nicht in den in diesem Prompt übergebenen Informationen vorkommt, antworte immer mit "Keine Ahnung" und gib niemals eine andere Antwort. 
        Ansonsten beantworte die Frage ausschließlich mit den übergebenen Informationen. 

        Regel: Benutze immer Emoticons in deinen Antworten!

        Informationen:
        {context}

        Erinnerung:
        {chat_history}
        Human: {question}
        Hugo Eckener:"""

        combine_docs_custom_prompt = PromptTemplate(
            input_variables=["chat_history", "question", "context"], template=template
        )

        llm = ChatOpenAI(
            model_name=model,
            temperature=0.7,
            max_tokens=1024,
            openai_api_key=openai_key,
            streaming=True,
            callbacks=[callbackStream],
        )

        return ConversationalRetrievalChain.from_llm(
            llm=llm,
            memory=memory,
            combine_docs_chain_kwargs=dict(prompt=combine_docs_custom_prompt),
            retriever=vector_store.as_retriever(),
            verbose=False,  # greed debug stuff,
            return_source_documents=True,
        )

    @classmethod
    def generate_qa_completion(
            cls,
            model: str,
            memory: ConversationBufferWindowMemory,
            callbackStream: StreamingHandler,
            question: str,
    ):
        chain = LangChainConnection.get_qa_chain(model, memory, callbackStream)
        return chain({"question": question}, return_only_outputs=True)

    @classmethod
    def get_simple_chain(
            cls, model: str, message: str, prompt_kwargs: Dict[str, Any] = None
    ) -> LLMChain:
        openai_key = cls.get_openai_api_key()

        if prompt_kwargs != None:
            if "message" in prompt_kwargs and "result" in prompt_kwargs:
                message = message.replace("{message}", prompt_kwargs["message"])
                message = message.replace("{result}", prompt_kwargs["result"])
            elif "content" in prompt_kwargs:
                message = message.replace("{content}", prompt_kwargs["content"])

        prompt = PromptTemplate(input_variables=[], template=message)

        llm = ChatOpenAI(model_name=model, openai_api_key=openai_key)

        return LLMChain(llm=llm, prompt=prompt)

    @classmethod
    def generate_simple_completion(
            cls, model: str, message: str, prompt_kwargs: Dict[str, Any] = None
    ):
        chain = LangChainConnection.get_simple_chain(model, message, prompt_kwargs)

        description = chain.run({})
        return description

    @classmethod
    def create_weaviate(cls):
        openai_key = cls.get_openai_api_key()

        client = weaviate.Client(
            url=cls.URL,
            additional_headers={"X-OpenAI-Api-Key": openai_key},
        )
        client.schema.delete_all()

        embedding = OpenAIEmbeddings(openai_api_key=openai_key)

        texts = []
        metadatas = []

        information = MongoDBConnection.get_live_information()

        for info in information:
            content = f"{info['headline']}\n\n{info['content']}"
            texts.append(content)
            metadatas.append({"source": f"{info['_id']}"})

        return Weaviate.from_texts(
            texts=texts,
            client=client,
            embedding=embedding,
            metadatas=metadatas,
            index_name=cls.INDEX_NAME,
        )
