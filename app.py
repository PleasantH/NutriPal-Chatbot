# Required installations:
# pip install google-genai streamlit fastapi uvicorn python-dotenv pydantic

import os
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

# Initialize Google GenAI client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
model = "gemini-2.5-pro"

# --------------------
# Pydantic Chat Model
# --------------------
class ChatInput(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

# --------------------
# NutriPal AI ChatBot Class
# --------------------
class NutriPalChatBot:
     def __init__(self, model_name=model):
        self.model = model_name
        prompt_text = (
            "You are NutriPal AI, a smart, compassionate African nutrition assistant trained to help users make informed food choices.\n"
            "- Understand local African cuisines, ingredients, and health contexts.\n"
            "- Provide medically sound, evidence-based dietary advice for conditions like diabetes, ulcers, hypertension, obesity, and malnutrition.\n"
            "- Help users navigate allergies, nutrient deficiencies, and create balanced diets.\n"
            "- Always answer respectfully, clearly, and like a certified dietitian or nutritionist.\n"
            "- Promote culturally relevant and accessible food alternatives.\n"
            "- Avoid suggesting Western meals unless requested, and instead localize food advice for African contexts (Nigeria, Ghana, Kenya, etc.).\n"
            "- Use an empathetic, encouraging tone to promote healthy eating habits and lifestyle improvement."
        )
        self.system_prompt = types.Content(
            role="user",
            parts=[
                types.Part(text=prompt_text)
            ]
        )

     def chat(self, user_input: str) -> str:
        contents = [
            self.system_prompt,
            types.Content(
                role="user",
                parts=[types.Part(text=user_input)]
            )
        ]

        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=-1),
            response_mime_type="text/plain"
        )

        reply = ""
        for chunk in client.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=generate_content_config,
        ):
            reply += chunk.text
        return reply.strip()

# Instantiate chatbot
chatbot = NutriPalChatBot()

# --------------------
# Streamlit App
# --------------------
st.set_page_config(page_title="NutriPal AI ChatBot", layout="centered")
st.title("🥗 NutriPal AI – Your Smart Nutrition Assistant")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

user_input = st.text_input("Ask me anything about your diet, allergies, or health needs:", key="user_input")

if st.button("Send") and user_input:
    response = chatbot.chat(user_input)
    st.session_state.chat_history.append((user_input, response))

for user, bot in reversed(st.session_state.chat_history):
    st.markdown(f"**You:** {user}")
    st.markdown(f"**NutriPal AI:** {bot}")


# To run Streamlit:
# streamlit run app.py
