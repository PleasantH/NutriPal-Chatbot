import os
import streamlit as st
import datetime
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load local .env only if not on Streamlit Cloud
if not st.secrets:
    load_dotenv()

api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("❌ Gemini API key not found.")

# Initialize Gemini client
client = genai.Client(api_key=api_key)
model = "gemini-2.5-pro"

# Page config
st.set_page_config(page_title="NutriPal AI 🍲", layout="wide")

# Session initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "diet_log" not in st.session_state:
    st.session_state.diet_log = []
if "meal_image" not in st.session_state:
    st.session_state.meal_image = None
    st.session_state.meal_image_bytes = None
    st.session_state.image_analysis = None

# System prompt
SYSTEM_PROMPT = types.Content(
    role="user",
    parts=[types.Part(text="""
       You are NutriPal AI, a compassionate African nutrition assistant. Your expertise is strictly limited to food, diet, nutrition, and health-related topics. You:

    - Specialize in African cuisines and dietary needs, with localized advice for Nigeria, Ghana, Kenya, etc.

    - Give only evidence-based, culturally relevant guidance and avoid recommending Western meals unless asked.

    - Support users in managing allergies, deficiencies, chronic conditions, and meal planning using affordable local options.

    - Respond only to food/health-related images (meals, ingredients, nutrition labels, symptoms).

    - If the image or question is unrelated (e.g., of people, places, furniture, or general topics), reply with:

    "I'm sorry, this is outside my scope of expertise but I can help you with any food or health related issue."

    - Always answer clearly, professionally, and empathetically—like a certified nutritionist.

    - If the request is unclear, ask for more details before answering.

    - Think carefully before responding. Never provide medical diagnoses, refer to a dietician or healthcare professional services.
    """)]
)

# SIDEBAR Navigation
with st.sidebar:
    st.title("🥗 NutriPal Tools")
    section = st.radio("Choose a Tool:", ["💬 Chat", "📷 Image Upload", "📅 Diet Tracker"])

# SECTION 1: CHAT
if section == "💬 Chat":
    st.markdown("<h1 style='text-align:center;'>NutriPal AI 👩‍⚕️</h1>", unsafe_allow_html=True)
    st.markdown("<h5 style='text-align:center; color:#555;'>Ask anything about your diet, food allergies, or healthy eating!</h5>", unsafe_allow_html=True)
    st.divider()

    # Show previous messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input prompt
    if prompt := st.chat_input("Ask something about your diet or health..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Gemini response
        chat_input = [SYSTEM_PROMPT, types.Content(role="user", parts=[types.Part(text=prompt)])]
        response = ""
        try:
            for chunk in client.models.generate_content_stream(model=model, contents=chat_input):
                response += chunk.text
        except Exception as e:
            response = f"⚠️ Error: {e}"

        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)

# SECTION 2: IMAGE UPLOAD
elif section == "📷 Image Upload":
    st.subheader("📸 Upload a Meal Image for Analysis")

    uploaded_image = st.file_uploader("Upload a picture of your food (jpg/png)", type=["jpg", "jpeg", "png"])

    if uploaded_image:
        st.session_state.meal_image = uploaded_image
        st.session_state.meal_image_bytes = uploaded_image.read()
        st.session_state.image_analysis = None  # Reset previous result

    if st.session_state.meal_image:
        st.image(st.session_state.meal_image, use_column_width=True, caption="Uploaded Meal")

        if st.button("🔍 Analyze Meal Image"):
            with st.spinner("Analyzing your image..."):
                image_prompt = types.Content(
                    role="user",
                    parts=[
                        types.Part(text="""
                            Analyze this image ONLY if it clearly shows food, meals, or something health-related.
                            If it's unrelated (e.g., people, furniture, scenery), politely respond:
                            'Sorry, I can only analyze food or health-related images.'
                        """),
                        types.Part(inline_data=types.Blob(
                            mime_type=st.session_state.meal_image.type,
                            data=st.session_state.meal_image_bytes
                        ))
                    ]
                )

                try:
                    image_response = ""
                    for chunk in client.models.generate_content_stream(model=model, contents=[image_prompt]):
                        image_response += chunk.text

                    st.session_state.image_analysis = image_response

                except Exception as e:
                    st.session_state.image_analysis = f"❌ Error during analysis: {e}"

    # Show image analysis
    if st.session_state.image_analysis:
        if "Sorry, I can only analyze food" in st.session_state.image_analysis:
            st.warning("⚠️ This image does not appear to be food- or health-related.")
        else:
            st.success("✅ Analysis Complete!")
            st.markdown("### 🍽️ Meal Analysis")
            st.markdown(st.session_state.image_analysis)

# SECTION 3: DIET TRACKER
elif section == "📅 Diet Tracker":
    st.subheader("📅 Track Your Meal & Water Intake")

    meal_type = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"])
    meal_description = st.text_area("What did you eat?", height=100)
    water_intake = st.slider("Water intake (cups)", 0, 10, 0)

    if st.button("➕ Log Entry"):
        entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "meal_type": meal_type,
            "description": meal_description,
            "water": water_intake
        }
        st.session_state.diet_log.append(entry)
        st.success("✅ Meal logged successfully!")

    if st.session_state.diet_log:
        st.markdown("### 🧾 Meal History")
        for entry in reversed(st.session_state.diet_log):
            st.markdown(f"**{entry['timestamp']}** — *{entry['meal_type']}* 🍽️")
            st.markdown(f"Meal: {entry['description']}  \nWater: {entry['water']} cups")
            st.markdown("---")


# To run Streamlit:
# streamlit run app.py
# venv\Scripts\activate
