import os
import json
import streamlit as st
import datetime
import smtplib
from dotenv import load_dotenv
from email.message import EmailMessage
from google import genai
from google.genai import types
from collections import defaultdict

# Load environment variables
if not st.secrets:
    load_dotenv()

api_key = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
user_email = st.secrets.get("USER_EMAIL") or os.getenv("USER_EMAIL")
email_password = st.secrets.get("EMAIL_PASSWORD") or os.getenv("EMAIL_PASSWORD")

if not api_key:
    st.error("❌ Gemini API key not found.")

client = genai.Client(api_key=api_key)
model = "gemini-2.5-pro"

st.set_page_config(page_title="NutriPal AI 🍲", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "diet_log" not in st.session_state:
    st.session_state.diet_log = []
if "meal_image" not in st.session_state:
    st.session_state.meal_image = None
    st.session_state.meal_image_bytes = None
    st.session_state.image_analysis = None

SYSTEM_PROMPT = types.Content(
    role="user",
    parts=[types.Part(text="""
        You are NutriPal AI, Africa's No.1 smart food and health assistant. Your focus is solely on:
        - African diets and nutrition,
        - Health tips for common African conditions,
        - Recognizing food-related images (not unrelated topics).

        Follow these rules:
        - If asked about non-food or health topics, politely decline.
        - Respond briefly and empathetically and like a certified African nutritionist.
        - Think carefully, ask clarifying questions if needed.
        - Never give medical diagnoses and refer them to a doctor.
        - Provide culturally relevant and local advice only.
        """)]
)

# Save diet logs to JSON
def save_log_json(user_email, entry):
    file_path = f"logs/{user_email}_diet_log.json"
    os.makedirs("logs", exist_ok=True)
    log_data = []
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            log_data = json.load(f)
    log_data.append(entry)
    with open(file_path, "w") as f:
        json.dump(log_data, f, indent=2)

# Send summary email (daily or weekly)
def send_summary_email(user_email, summary_type="daily"):
    try:
        sender = user_email
        password = email_password

        log_path = f"logs/{user_email}_diet_log.json"
        if not os.path.exists(log_path):
            return "⚠️ No diet log found for this user."

        with open(log_path, "r") as f:
            logs = json.load(f)

        summary = defaultdict(lambda: {"meals": [], "water": 0})
        for entry in logs:
            key = entry["date"] if summary_type == "daily" else entry["timestamp"][:7]
            summary[key]["meals"].append(f"{entry['meal_type']}: {entry['description']}")
            summary[key]["water"] += entry["water"]

        summary_text = f"NutriPal {summary_type.capitalize()} Summary for {user_email}\n\n"
        for date, data in summary.items():
            summary_text += f"📅 {date}\n"
            summary_text += "Meals:\n" + "\n".join(["- " + m for m in data["meals"]]) + "\n"
            summary_text += f"💧 Water: {data['water']} cups\n\n"

        msg = EmailMessage()
        msg["Subject"] = f"NutriPal {summary_type.capitalize()} Summary"
        msg["From"] = sender
        msg["To"] = user_email
        msg.set_content(summary_text)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)

        return "✅ Summary sent to your email!"
    except Exception as e:
        return f"❌ Failed to send summary: {e}"

# Generate summary from current session
def generate_summary(log_data, mode="daily"):
    summary = defaultdict(lambda: {"meals": [], "water": 0})
    for entry in log_data:
        key = entry["date"] if mode == "daily" else entry["timestamp"][:7]
        summary[key]["meals"].append(f"{entry['meal_type']}: {entry['description']}")
        summary[key]["water"] += entry["water"]
    return summary

with st.sidebar:
    st.title("🥗 NutriPal Tools")
    section = st.radio("Choose a Tool:", ["💬 Chat", "📷 Image Upload", "📅 Diet Tracker"])

if section == "💬 Chat":
    st.markdown("<h1 style='text-align:center;'>NutriPal AI 👩‍⚕️</h1>", unsafe_allow_html=True)
    st.markdown("<h5 style='text-align:center; color:#555;'>Ask about African diets, allergies, or health tips.</h5>", unsafe_allow_html=True)
    st.divider()

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask something about your diet or health..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        few_shot_examples = types.Content(role="user", parts=[types.Part(text="What’s a healthy Nigerian breakfast?")])

        chat_input = [SYSTEM_PROMPT, few_shot_examples, types.Content(role="user", parts=[types.Part(text=prompt)])]
        response = ""
        try:
            for chunk in client.models.generate_content_stream(model=model, contents=chat_input):
                response += chunk.text
        except Exception as e:
            response = f"⚠️ Error: {e}"

        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)

elif section == "📷 Image Upload":
    st.subheader("📸 Upload a Meal Image for Analysis")
    uploaded_image = st.file_uploader("Upload a picture of your food", type=["jpg", "jpeg", "png"])

    if uploaded_image:
        st.session_state.meal_image = uploaded_image
        st.session_state.meal_image_bytes = uploaded_image.read()
        st.session_state.image_analysis = None

    if st.session_state.meal_image:
        st.image(st.session_state.meal_image, use_column_width=True)
        if st.button("🔍 Analyze Meal Image"):
            with st.spinner("Analyzing image..."):
                image_prompt = types.Content(
                    role="user",
                    parts=[
                        types.Part(text="Analyze only food or health-related image. Ignore irrelevant items."),
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
                    st.session_state.image_analysis = f"❌ Error: {e}"

    if st.session_state.image_analysis:
        st.markdown("### 🍽️ Meal Analysis")
        st.markdown(st.session_state.image_analysis)

elif section == "📅 Diet Tracker":
    st.subheader("📅 Track Your Meals")
    email = st.text_input("Enter your email")
    meal_type = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"])
    meal_description = st.text_area("What did you eat?")
    water_intake = st.slider("Water intake (cups)", 0, 10, 0)

    if st.button("➕ Log Entry"):
        now = datetime.datetime.now()
        entry = {
            "timestamp": now.strftime("%Y-%m-%d %H:%M"),
            "meal_type": meal_type,
            "description": meal_description,
            "water": water_intake,
            "date": now.strftime("%Y-%m-%d"),
            "email": email
        }
        st.session_state.diet_log.append(entry)
        save_log_json(email, entry)
        st.success("✅ Meal logged!")

    if st.session_state.diet_log:
        st.markdown("### 🧾 Your Log")
        for entry in reversed(st.session_state.diet_log):
            st.markdown(f"**{entry['timestamp']}** — *{entry['meal_type']}* 🍽️")
            st.markdown(f"Meal: {entry['description']}  \nWater: {entry['water']} cups")
            st.markdown("---")

        # Summary Generator
        with st.expander("📊 View Summary"):
            daily = generate_summary(st.session_state.diet_log, mode="daily")
            weekly = generate_summary(st.session_state.diet_log, mode="weekly")

            st.write("### 📅 Daily Summary")
            for date, data in daily.items():
                st.markdown(f"**{date}**")
                st.markdown("Meals: " + ", ".join(data["meals"]))
                st.markdown(f"Water: {data['water']} cups")

            st.write("### 📆 Weekly Summary")
            for week, data in weekly.items():
                st.markdown(f"**Week: {week}**")
                st.markdown("Meals: " + ", ".join(data["meals"]))
                st.markdown(f"Water: {data['water']} cups")

        # Email Buttons
        if st.button("📧 Send My Daily Summary"):
            result = send_summary_email(email, summary_type="daily")
            st.info(result)

        if st.button("📆 Send My Weekly Summary"):
            result = send_summary_email(email, summary_type="weekly")
            st.info(result)


# To run Streamlit:
# streamlit run app.py