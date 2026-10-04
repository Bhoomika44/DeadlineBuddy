
import json

import streamlit as st
from google import genai
from google.genai import types
from twilio.rest import Client as TwilioClient

from prompts import (
    SUMMARY_REQUEST_PROMPT,
    SYSTEM_PROMPT,
    WELCOME_MESSAGE_TEMPLATE
)


# --------------------------------------------------
# Configuration
# --------------------------------------------------

MODEL_NAME = "gemini-3.8-flash"

st.set_page_config(
    page_title="DeadlineBuddy",
    page_icon="📅"
)


# --------------------------------------------------
# API Keys
# --------------------------------------------------

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]
TWILIO_WHATSAPP_FROM = st.secrets["TWILIO_WHATSAPP_FROM"]
TWILIO_CONTENT_SID = st.secrets["TWILIO_CONTENT_SID"]


# --------------------------------------------------
# Clients
# --------------------------------------------------

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


@st.cache_resource
def get_twilio_client():
    return TwilioClient(
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN
    )


gemini_client = get_gemini_client()
twilio_client = get_twilio_client()


# --------------------------------------------------
# Render messages
# --------------------------------------------------

def render_message(message):

    with st.chat_message(message["role"]):

        if message["kind"] == "text":
            st.write(message["content"])

        elif message["kind"] == "image":
            st.image(message["content"])


# --------------------------------------------------
# Add message
# --------------------------------------------------

def add_message(role, kind, content):

    st.session_state.messages.append(
        {
            "role": role,
            "kind": kind,
            "content": content
        }
    )

    render_message(
        st.session_state.messages[-1]
    )


# --------------------------------------------------
# Ask Gemini
# --------------------------------------------------

def ask_gemini(parts):

    try:

        response = st.session_state.chat.send_message(parts)

        return response.text

    except Exception as error:

        return f"Sorry, something went wrong: {error}"


# --------------------------------------------------
# Clean WhatsApp message
# --------------------------------------------------

def clean_whatsapp_text(text):

    if not text:
        return "No deadline summary available."

    text = " ".join(text.split())

    return (
        text[:1500] + "..."
        if len(text) > 1500
        else text
    )


# --------------------------------------------------
# Send WhatsApp
# --------------------------------------------------

def send_whatsapp(to_number, user_name, summary):

    try:

        content_variables = json.dumps(
            {
                "1": user_name,
                "2": clean_whatsapp_text(summary)
            },
            ensure_ascii=False
        )

        message = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{to_number}",
            content_sid=TWILIO_CONTENT_SID,
            content_variables=content_variables,
        )

        return True, message.sid

    except Exception as error:

        return False, str(error)


# --------------------------------------------------
# Step 1: Onboarding
# --------------------------------------------------

if "onboarded" not in st.session_state:

    st.title("📅 DeadlineBuddy")

    st.caption(
        "Snap it. Track it. Never miss a deadline."
    )

    with st.form("onboarding_form"):

        name = st.text_input(
            "Your name"
        )

        whatsapp_number = st.text_input(
            "WhatsApp number (with country code)",
            placeholder="+91XXXXXXXXXX",
            help="DeadlineBuddy will send your deadline summary to this number."
        )

        submitted = st.form_submit_button(
            "Let's go 🚀"
        )

    if submitted:

        if not name.strip() or not whatsapp_number.strip():

            st.warning(
                "Please fill in both your name and WhatsApp number."
            )

        else:

            st.session_state.name = name.strip()

            st.session_state.whatsapp_number = (
                whatsapp_number.strip()
            )

            st.session_state.chat = gemini_client.chats.create(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT
                ),
            )

            st.session_state.messages = []

            st.session_state.onboarded = True

            st.rerun()

    st.stop()


# --------------------------------------------------
# Step 2: Main interface
# --------------------------------------------------

header_col, button_col = st.columns(
    [5, 2],
    vertical_alignment="center"
)


with header_col:

    st.title("📅 DeadlineBuddy")


with button_col:

    send_disabled = (
        len(st.session_state.messages) <= 1
    )

    if st.button(
        "📤 Send to WhatsApp",
        disabled=send_disabled,
        use_container_width=True
    ):

        with st.spinner(
            "Summarizing your deadlines..."
        ):

            summary = ask_gemini(
                [SUMMARY_REQUEST_PROMPT]
            )

        success, info = send_whatsapp(
            st.session_state.whatsapp_number,
            st.session_state.name,
            summary
        )

        if success:

            st.success(
                "Sent! Check your WhatsApp 📲"
            )

        else:

            st.error(
                f"Couldn't send that: {info}"
            )


# --------------------------------------------------
# User information
# --------------------------------------------------

st.caption(
    f"Logged in as {st.session_state.name} "
    f"• Reminders go to {st.session_state.whatsapp_number}"
)


# --------------------------------------------------
# Display chat history
# --------------------------------------------------

if not st.session_state.messages:

    add_message(
        "assistant",
        "text",
        WELCOME_MESSAGE_TEMPLATE.format(
            name=st.session_state.name
        )
    )

else:

    for message in st.session_state.messages:

        render_message(message)


# --------------------------------------------------
# Chat input
# --------------------------------------------------

user_input = st.chat_input(
    "Ask about deadlines or attach a syllabus/timetable photo",
    accept_file=True,
    file_type=["jpg", "jpeg", "png"],
)


# --------------------------------------------------
# Process user input
# --------------------------------------------------

if user_input:

    photo = (
        user_input.files[0]
        if user_input.files
        else None
    )

    text = user_input.text

    parts = []


    # ----------------------------------------------
    # Process image
    # ----------------------------------------------

    if photo is not None:

        photo_bytes = photo.getvalue()

        add_message(
            "user",
            "image",
            photo_bytes
        )

        parts.append(
            types.Part.from_bytes(
                data=photo_bytes,
                mime_type=photo.type
            )
        )


    # ----------------------------------------------
    # Process text
    # ----------------------------------------------

    if text:

        add_message(
            "user",
            "text",
            text
        )

        parts.append(text)


    # ----------------------------------------------
    # Image without text
    # ----------------------------------------------

    elif photo is not None:

        parts.append(
            """
            Analyze this syllabus, timetable, assignment sheet,
            or academic document.

            Extract all deadlines, submission dates, exam dates,
            project dates, quiz dates, lab dates, and other
            important dates.

            For each deadline, clearly provide:
            1. Date
            2. Task or assignment
            3. Subject or course
            4. Important details

            If a date is unclear, say that it is unclear.
            Do not invent dates.
            """
        )


    # ----------------------------------------------
    # Gemini response
    # ----------------------------------------------

    with st.spinner(
        "Scanning for deadlines..."
    ):

        answer = ask_gemini(parts)


    add_message(
        "assistant",
        "text",
        answer
    )
