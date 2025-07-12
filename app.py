# nutripal_app.py

import os
import streamlit as st
import datetime
import json
import smtplib
import schedule
import threading
import time
from email.mime.text import MIMEText
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load env variables
if not st.secrets:
    load_dotenv()

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY")
USER_EMAIL = st.secrets.get("USER_EMAIL") or os.getenv("USER_EMAIL")
EMAIL_PASSWORD = st.secrets.get("EMAIL_PASSWORD") or os.getenv("EMAIL_PASSWORD")

# Initialize Gemini client
client = genai.Client(api_key=GEMINI_API_KEY)
model = "gemini-2.5-pro"

# Persistent user memory folder
os.makedirs("nutripal_users", exist_ok=True)

# System Prompt
SYSTEM_PROMPT = types.Content(
    role="user",
    parts=[types.Part(text="""
You are NutriPal AI, Africa’s No.1 food and health companion. Your job is to offer culturally relevant nutrition advice in a warm, friendly, and professional tone.

You MUST follow these strict guidelines:

- You ONLY answer questions related to food, diet, nutrition, or health conditions affecting Africans.
- If a user greets you (e.g., says “hi”, “hello”), respond with: “Hello! How can I help you today with your food or health questions?”
- Never assume what the user meant. Only respond to what was asked. Don’t give extra advice unless they asked for it.
- If the question is vague, politely ask them to clarify before answering.
- Do not provide medical diagnoses. Always refer users to a healthcare professional for those concerns.
- If the user sends a non-food or non-health-related image or question, respond with: “Sorry, I can only help with food or health-related topics.”

You specialize in African cuisine, meal planning, water intake, food allergies, and dietary deficiencies common in regions like Nigeria, Ghana, and Kenya.
    """)]
)

# Save logs per user
def save_user_data(email, meal_type, description, water):
    user_file = f"nutripal_users/{email}.json"
    now = datetime.datetime.now()
    entry = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M"),
        "meal_type": meal_type,
        "description": description,
        "water": water
    }
    data = {"logs": []}
    if os.path.exists(user_file):
        with open(user_file, 'r') as f:
            data = json.load(f)
    data["logs"].append(entry)
    with open(user_file, 'w') as f:
        json.dump(data, f, indent=2)
    return entry

# Generate Summary
def generate_summary(email):
    file_path = f"nutripal_users/{email}.json"
    if not os.path.exists(file_path):
        return None

    with open(file_path) as f:
        data = json.load(f)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    today_logs = [log for log in data["logs"] if log["timestamp"].startswith(today)]

    if not today_logs:
        return None

    water_total = sum(log['water'] for log in today_logs)
    meal_summary = "\n\n".join([
        f"{log['timestamp']} — {log['meal_type']}: {log['description']} (Water: {log['water']} cups)"
        for log in today_logs
    ])

    # Multistep logic engine
    suggestions = []
    if water_total < 4:
        suggestions.append("Your water intake today was low. Consider drinking coconut water, zobo, or eating watermelon.")
    rice_meals = sum('rice' in log['description'].lower() for log in today_logs)
    if rice_meals >= 3:
        suggestions.append("You've had rice multiple times today. Try adding more vegetables like efo riro or okra.")

    summary = f"Daily Summary for {today}\n\n{meal_summary}\n\nTotal Water Intake: {water_total} cups"
    if suggestions:
        summary += "\n\nSuggestions:\n" + "\n".join(suggestions)

    return summary

# Send Email
def send_email_summary(email, content):
    try:
        msg = MIMEText(content)
        msg['Subject'] = 'NutriPal Daily Nutrition Summary'
        msg['From'] = USER_EMAIL
        msg['To'] = email

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(USER_EMAIL, EMAIL_PASSWORD)
            server.sendmail(USER_EMAIL, email, msg.as_string())
    except Exception as e:
        print(f"❌ Failed to send summary to {email}: {e}")

# Schedule Task
def schedule_summaries():
    def job():
        for filename in os.listdir("nutripal_users"):
            if filename.endswith(".json"):
                email = filename.replace(".json", "")
                summary = generate_summary(email)
                if summary:
                    send_email_summary(email, summary)
    schedule.every().day.at("21:00").do(job)

    while True:
        schedule.run_pending()
        time.sleep(60)

# Background thread for scheduler
threading.Thread(target=schedule_summaries, daemon=True).start()

# Streamlit UI
st.set_page_config(page_title="NutriPal AI 🍲", layout="wide")
st.markdown("<h1 style='text-align:center;'>NutriPal AI 👩‍⚕️</h1>", unsafe_allow_html=True)

with st.sidebar:
    user_email = st.text_input("Enter your email")
    section = st.radio("Choose a Tool", ["💬 Chat", "📷 Image Upload", "📅 Log Meals"])

if section == "💬 Chat":
    st.subheader("Ask about your food, diet or allergies")
    if "chat" not in st.session_state:
        st.session_state.chat = []
    for msg in st.session_state.chat:
        with st.chat_message(msg['role']):
            st.markdown(msg['content'])

    if prompt := st.chat_input("Ask NutriPal AI..."):
        st.session_state.chat.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        input_prompt = [SYSTEM_PROMPT, types.Content(role="user", parts=[types.Part(text=prompt)])]
        reply = ""
        try:
            for chunk in client.models.generate_content_stream(model=model, contents=input_prompt):
                reply += chunk.text
        except Exception as e:
            reply = f"❌ Error: {e}"

        st.session_state.chat.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)

elif section == "📷 Image Upload":
    st.subheader("Upload a food image")
    file = st.file_uploader("Upload meal photo", type=["jpg", "png"])

    if file and user_email:
        image_bytes = file.read()
        image_prompt = types.Content(
            role="user",
            parts=[
                types.Part(text="""
                    Analyze this image ONLY if it shows food or health-related items.
                    If not, say: 'Sorry, I can only analyze food or health-related images.'
                """),
                types.Part(inline_data=types.Blob(mime_type=file.type, data=image_bytes))
            ]
        )
        with st.spinner("Analyzing..."):
            try:
                output = ""
                for chunk in client.models.generate_content_stream(model=model, contents=[image_prompt]):
                    output += chunk.text
                st.success("Done!")
                st.markdown(output)
            except Exception as e:
                st.error(f"❌ Error: {e}")

elif section == "📅 Log Meals":
    st.subheader("Log your meals")
    if user_email:
        meal_type = st.selectbox("Meal Type", ["Breakfast", "Lunch", "Dinner", "Snack"])
        desc = st.text_area("What did you eat?")
        water = st.slider("Water (cups)", 0, 10, 0)
        if st.button("Log Entry"):
            entry = save_user_data(user_email, meal_type, desc, water)
            st.success("Logged successfully!")
            st.markdown(f"**{entry['timestamp']}** — *{entry['meal_type']}* 🍽️")
            st.markdown(f"Meal: {entry['description']}  \nWater: {entry['water']} cups")
    else:
        st.warning("Please enter your email in the sidebar.")


# To run Streamlit:
# streamlit run app.py