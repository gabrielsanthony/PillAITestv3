import streamlit as st
import openai
import os
import re
import base64
import json
import time  # at the top of your file
from deep_translator import GoogleTranslator
from datetime import datetime, timedelta

import re

# code for extracing medicines name duration and timing from the answer
def extract_medicine_name(question):
    # Looks for common medicine inquiry phrases
    match = re.search(r"(?:take|use|about|for)\s+([A-Za-z0-9\-]+)", question, re.IGNORECASE)
    return match.group(1) if match else "Medication"

def extract_duration_days(answer):
    match = re.search(r"for (\d+) days?", answer)
    return int(match.group(1)) if match else 7

def extract_dose_times(answer):
    times = []
    if "once a day" in answer or "once daily" in answer:
        times = ["08:00"]
    elif "twice" in answer:
        times = ["08:00", "20:00"]
    elif "three times" in answer:
        times = ["08:00", "14:00", "20:00"]
    elif "every 8 hours" in answer:
        times = ["06:00", "14:00", "22:00"]
    elif "every 12 hours" in answer:
        times = ["08:00", "20:00"]
    else:
        times = ["08:00"]  # fallback
    return [datetime.strptime(t, "%H:%M").time() for t in times]

# delay to speed up
max_wait = 15  # seconds
elapsed = 0

# Page config
st.set_page_config(page_title="Pill-AI 3.0", page_icon="💊", layout="wide")

# Custom CSS
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari&family=Noto+Sans+SC&display=swap" rel="stylesheet">
    <style>
    body {
        background: linear-gradient(to bottom right, #f4f6f9, #e0f7fa);
        font-family: 'Segoe UI', sans-serif;
    }
    html[lang='zh'] body { font-family: 'Noto Sans SC', sans-serif !important; }
    .stTextInput input {
        background-color: #eeeeee !important;
        color: #000000 !important;
        font-size: 1.2em !important;
        padding: 10px !important;
        border: 2px solid black !important;
        border-radius: 6px !important;
        box-shadow: none !important;
    }
    div:empty { display: none !important; }
    .stTextInput input:focus { border: 2px solid orange !important; outline: none !important; }
    .stButton button {
        background-color: #3b82f6;
        color: white;
        font-size: 1.1em;
        padding: 0.6em 1em;
        border-radius: 8px;
        margin-top: 4px;
        width: 100%;
    }
    .stButton button:hover {
        background-color: #3b82f6;
        color: white;
        font-size: 1.5em;
    }
      .stButton button:focus {
    background-color: #2563eb !important;
    color: white !important;
    outline: none !important;
    box-shadow: none !important;
}
    .stButton button:active {
    background-color: #2563eb !important;
    color: white !important;
    outline: none !important;
    box-shadow: none !important;
}


    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    .section {
        background-color: #ffffff;
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin-bottom: 2rem;
    }
    @keyframes float {
        0% { transform: translateY(0px); }
        50% { transform: translateY(-6px); }
        100% { transform: translateY(0px); }
    }
    img[src*="pillai_logo"] {
        animation: float 3s ease-in-out infinite;
    }
    .stSelectbox div[data-baseweb="select"] {
        margin-top: 6px;
        font-size: 1.05em;
        padding: 6px;
    }
    .stSelectbox div[data-baseweb="select"] > div {
        border: 1px solid #ccc !important;
        border-radius: 6px !important;
    }
    .stSelectbox div[data-baseweb="select"]:hover {
        border-color: #999 !important;
    }
    /* Reduce margin below the language dropdown */
    div[data-testid="stSelectbox"] {
    margin-bottom: 0.3rem !important;
    }
    @media (max-width: 768px) {
    .stTextInput input {
        font-size: 1em !important;
    }
    .stButton button {
        font-size: 1em !important;
        color: white;
        padding: 0.6em !important;
    }
    </style>
""", unsafe_allow_html=True)

# Logo
def get_base64_image(path):
    with open(path, "rb") as img_file:
        return f"data:image/png;base64,{base64.b64encode(img_file.read()).decode()}"

if os.path.exists("pillai_logo.png"):
    logo_base64 = get_base64_image("pillai_logo.png")
    st.markdown(f"<div style='text-align: center;'><img src='{logo_base64}' width='240' style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)

# Language selector
language = st.selectbox("\U0001f310 Choose answer language:", ["English", "Te Reo Māori", "Samoan", "Mandarin"])

labels = {
    "English": {
        #"prompt": "Ask a medicine question:",
        "placeholder": "💡 Ask a medication related question",
        "send": "Send",
        "thinking": "Thinking...",
       # "tagline": "Helping Kiwis understand medicines, safely.",
        "empty": "Please enter a question.",
        "error": "The assistant failed to complete the request.",
        "disclaimer": "⚠️ Pill-AI is not a substitute for professional advice from your pharmacist or doctor. Please contact them or Healthline (0800 611 116) if you have any questions or concerns.",
        "privacy_title": "🔐 Privacy Policy – Click to expand",
        "privacy": """### 🛡️ Pill-AI Privacy Policy (Prototype Version)

Welcome to Pill-AI — your trusted medicines advisor. This is a prototype to test if a tool like this can help people learn about their medicines using trusted Medsafe resources.

**📌 What we collect**  
– The questions you type into the chat box  

**🔁 Who else is involved**  
– OpenAI (for generating answers)  
– Streamlit (to host the app)  
– Google (for hosting and analytics)

**👶 Users under 16**  
We don’t ask for names, emails, or any personal information.

**🗑️ Temporary data**  
All data will be deleted after testing. This is a prototype.

**📬 Questions?**  
Contact us: pillai.nz.contact@gmail.com

*Pill-AI is not a substitute for professional medical advice.*"""
    },
    "Te Reo Māori": {
      #  "prompt": "Pātaihia tētahi pātai e pā ana ki te rongoā:",
        "placeholder": "💡 Hei tauira: Ka pai rānei te tango i te ibuprofen me te Panadol?",
        "send": "Tukua",
        "thinking": "E whakaaro ana...",
      #  "tagline": "Āwhinatia ngā Kiwi kia mārama ki ā rātou rongoā mā ngā kōrero mai i a Medsafe.",
        "empty": "Tēnā koa, tuhia he pātai.",
        "error": "I rahua te kaiawhina ki te whakaoti i te tono.",
        "disclaimer": "⚠️ Ehara a Pill-AI i te kaiārahi hauora tōtika. Me toro atu ki te rata, te kai rongoā rānei.",
        "privacy_title": "🔐 Kaupapahere Tūmataiti – Pāwhiritia kia kite",
        "privacy": """### 🛡️ Kaupapahere Tūmataiti o Pill-AI (Putanga Whakamātau)

Nau mai ki a Pill-AI — tō kaiāwhina rongoā pono. He putanga whakamātau tēnei hei āwhina i te iwi kia mārama ki ā rātou rongoā mā ngā rauemi Medsafe.

**📌 Ka kohia**  
– Ngā pātai ka tuhia e koe  

**🔁 Ko wai anō e uru ana**  
– OpenAI (hei hanga whakautu)  
– Streamlit (hei tuku i te pae tukutuku)  
– Google (hei manaaki me te aromātai)

**👶 Tamariki i raro i te 16**  
Kāore mātou e tono mō ō ingoa, īmēra, rānei.

**🗑️ Raraunga poto noa**  
Ka mukua katoatia ngā raraunga i muri i te wā whakamātau. He putanga whakamātau tēnei.

**📬 Pātai?**  
Whakapā mai: pillai.nz.contact@gmail.com

*Ehara a Pill-AI i te whakakapi mō ngā tohutohu hauora.*"""
    },
    "Samoan": {
     #   "prompt": "Fesili i se fesili e uiga i fualaau:",
        "placeholder": "💡 Fa'ata'ita'iga: E mafai ona ou inuina le ibuprofen ma le Panadol?",
        "send": "Auina atu",
        "thinking": "O mafaufau...",
      #  "tagline": "Fesoasoani i tagata Niu Sila ia malamalama i a latou fualaau e ala i fa'amatalaga fa'atuatuaina mai le Medsafe.",
        "empty": "Fa'amolemole tusia se fesili.",
        "error": "Le mafai e le fesoasoani ona tali atu.",
        "disclaimer": "⚠️ E le suitulaga Pill-AI i se foma'i moni. Fa'amolemole fa'afeso'ota'i se foma'i po'o se fomai fai fualaau.",
        "privacy_title": "🔐 Faiga Fa'alilolilo – Kiliki e faitau",
        "privacy": """### 🛡️ Faiga Fa'alilolilo a Pill-AI (Fa'ata'ita'iga)

Afio mai i Pill-AI — lau fesoasoani i fualaau. O se fa'ata'ita'iga lenei e fesoasoani i tagata ia malamalama i fualaau e fa'aaogaina ai fa'amatalaga mai Medsafe.

**📌 Mea matou te pueina**  
– Fesili e te tusia i le pusa fesili  

**🔁 O ai e fesoasoani**  
– OpenAI (mo tali atamai)  
– Streamlit (mo le upega tafa'ilagi)  
– Google (mo le talimalo ma le iloiloga)

**👶 I lalo o le 16 tausaga**  
Matou te le aoina ni igoa, imeli, po'o fa'amatalaga patino.

**🗑️ Fa'amatalaga le tumau**  
O fa'amatalaga uma o le a tapea pe a uma le vaitaimi o le fa'ata'ita'iga.

**📬 Fesili?**  
Imeli: pillai.nz.contact@gmail.com

*Pill-AI e le suitulaga i fautuaga fa'apolofesa tau soifua mālōlōina.*"""
    },
    "Mandarin": {
  #      "prompt": "请提出一个与药物有关的问题：",
        "placeholder": "💡 例如：布洛芬和扑热息痛可以一起吃吗？",
        "send": "发送",
        "thinking": "思考中...",
   #     "tagline": "通过 Medsafe 的可靠信息帮助新西兰人了解他们的药物。",
        "empty": "请输入一个问题。",
        "error": "助手未能完成请求。",
        "disclaimer": "⚠️ Pill-AI 不能替代专业医疗建议。请咨询医生或药剂师。",
        "privacy_title": "🔐 隐私政策 – 点击展开",
        "privacy": """### 🛡️ Pill-AI 隐私政策（测试版）

欢迎使用 Pill-AI —— 您值得信赖的用药助手。本工具为测试版本，帮助用户通过 Medsafe 学习药品信息。

**📌 我们收集的信息**  
– 您在对话框中输入的问题  

**🔁 涉及的平台**  
– OpenAI（用于生成回答）  
– Streamlit（用于网站托管）  
– Google（托管和分析）

**👶 16岁以下用户**  
我们不会索取您的姓名、电邮或其他个人信息。

**🗑️ 数据处理**  
这是一个测试版本。所有数据将在测试结束后删除。

**📬 联系方式**  
邮箱：pillai.nz.contact@gmail.com

*Pill-AI 并不能替代专业医疗建议。*"""
    }
}


# Get selected labels
L = labels.get(language, labels["English"])

medsafe_footers = {
    "English": "\n\n---\n_This information has been sourced from Medsafe NZ._ [https://www.medsafe.govt.nz/medicines/infoSearch.asp](https://www.medsafe.govt.nz/medicines/infoSearch.asp)",
    "Te Reo Māori": "\n\n---\n_I ahu mai tēnei pārongo i Medsafe Aotearoa._ [https://www.medsafe.govt.nz/medicines/infoSearch.asp](https://www.medsafe.govt.nz/medicines/infoSearch.asp)",
    "Samoan": "\n\n---\n_O lenei fa'amatalaga e sau mai Medsafe Niu Sila._ [https://www.medsafe.govt.nz/medicines/infoSearch.asp](https://www.medsafe.govt.nz/medicines/infoSearch.asp)",
    "Mandarin": "\n\n---\n_本信息来自新西兰 Medsafe。_ [https://www.medsafe.govt.nz/medicines/infoSearch.asp](https://www.medsafe.govt.nz/medicines/infoSearch.asp)"
}
medsafe_footer = medsafe_footers.get(language, medsafe_footers["English"])

# OpenAI setup
api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("OpenAI API key is not configured.")
    st.stop()

client = openai.OpenAI(api_key=api_key)
ASSISTANT_ID = "asst_dslQlYKM5FYGVEWj8pu7afAt"

lang_codes = {"Te Reo Māori": "mi", "Samoan": "sm", "Mandarin": "zh-CN"}

# UI Section
st.markdown("<div class='section'>", unsafe_allow_html=True)
#st.write(f"### 💬 {L['prompt']}")

# 🔁 Replace old input/button columns with this responsive block
st.markdown("""
<style>
.responsive-input-container {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-top: 12px;
    margin-bottom: 6px;
}

.responsive-input-container input {
    flex-grow: 1;
    min-width: 200px;
    padding: 10px;
    font-size: 1.1em;
    border: 2px solid black;
    border-radius: 6px;
    background-color: #eeeeee;
    color: black;
}

.responsive-input-container button {
    padding: 10px 16px;
    font-size: 1.1em;
    border-radius: 6px;
    border: none;
    background-color: #3b82f6;
    color: white;
    cursor: pointer;
    white-space: nowrap;
}

@media (max-width: 768px) {
    .responsive-input-container {
        flex-direction: column;
        align-items: stretch;
    }

    .responsive-input-container input,
    .responsive-input-container button {
        width: 100% !important;
    }
}
</style>

<div class="responsive-input-container">
""", unsafe_allow_html=True)

# Create text input inline
user_question = st.text_input(
    label="",
    placeholder=L["placeholder"],
    label_visibility="collapsed",
    key="question_input"
)

# Manually insert the send button next to the input
send_button = st.button(L["send"], use_container_width=False)

# Close the flexbox container
st.markdown("</div>", unsafe_allow_html=True)
# Add a short reminder below the input + send buttons
st.markdown(
    "<div style='text-align: left; color: orange; font-size: 1em; font-weight: bold; margin-top: 0.2rem;'>"
    "⚠️ Pill-AI is a prototype for testing purposes only and MUST NOT be relied upon for health advice. Please contact your doctor or pharmacist if you have any questions about your health or medications."
    "</div>",
    unsafe_allow_html=True
)

# Add toggles BELOW the input box and send button
col_center = st.columns([1, 2, 1])
with col_center[1]:
    with st.container():
        st.markdown("""
            <style>
            div[data-testid="stHorizontalBlock"] {
                display: flex;
                flex-direction: column;
                align-items: flex-start;
                gap: 0.1rem;
                margin-top: -0.5rem;
                margin-bottom: 0.5rem;
            }
            label[data-testid="stToggle"] {
                font-size: 1.05em;
                font-weight: 500;
                padding-top: 0.1rem;
                padding-bottom: 0.1rem;
            }
            </style>
        """, unsafe_allow_html=True)
        explain_like_12 = st.toggle("✨ Simplify the answer's language", value=False, key="simplify_toggle")
        use_memory = st.toggle("🧠 Memorise previous answers for context in follow-up questions", value=False, key="memory_toggle")

if use_memory and "thread_id" not in st.session_state:
    st.session_state["thread_id"] = client.beta.threads.create().id

# Override send_clicked to work with button
send_clicked = send_button and user_question.strip() != ""


# Add space
st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)

# Treat any non-empty question as a trigger (ENTER pressed)
if send_clicked:
    st.session_state["question_submitted"] = user_question


if send_clicked:
    if not user_question.strip():
        st.warning(L["empty"])
    else:
        with st.spinner(f"💬 {L['thinking']}"):
            try:
                adjusted_question = user_question
                if explain_like_12:
                    adjusted_question += " Please explain this in simple language suitable for a 12-year-old (I am not actually 12 though, don’t use slang or colloquialisms, be encouraging)."

                if use_memory:
                    # Use memory mode
                    client.beta.threads.messages.create(
                        thread_id=st.session_state["thread_id"],
                        role="user",
                        content=adjusted_question
                    )
                    run = client.beta.threads.runs.create(
                        thread_id=st.session_state["thread_id"],
                        assistant_id=ASSISTANT_ID
                    )
                    while True:
                        run_status = client.beta.threads.runs.retrieve(
                            thread_id=st.session_state["thread_id"],
                            run_id=run.id
                        )
                        if run_status.status in ["completed", "failed"]:
                            break
                    if run_status.status == "completed":
                        messages = client.beta.threads.messages.list(
                            thread_id=st.session_state["thread_id"], limit=1
                        )
                        raw_answer = messages.data[0].content[0].text.value
                    else:
                        raise RuntimeError("Threaded memory response failed.")

                else:
                    # Use fast chat model with no memory
                    chat_response = client.chat.completions.create(
                        model="gpt-4",
                        messages=[{"role": "user", "content": adjusted_question}]
                    )
                    raw_answer = chat_response.choices[0].message.content

                # Clean and translate if needed
                cleaned = re.sub(r'【[^】]*】', '', raw_answer).strip()
                if language != "English" and language in lang_codes:
                    translated = GoogleTranslator(source='auto', target=lang_codes[language]).translate(cleaned)
                    st.success(translated + medsafe_footer)
                else:
                    st.success(cleaned + medsafe_footer)
                  # --- Extract data for reminder ---
                med_name = extract_medicine_name(user_question)
                duration_days = extract_duration_days(cleaned)
                dose_times = extract_dose_times(cleaned)
                except Exception as e:
                    st.error(f"{L['error']} \n\nDetails: {str(e)}")

            # --- Extract data for reminder ---
med_name = extract_medicine_name(user_question)
duration_days = extract_duration_days(cleaned)
dose_times = extract_dose_times(cleaned)

# UI for reminder builder
st.markdown("### ⏰ Set a Calendar Reminder")

med_name_input = st.text_input("Medicine Name", value=med_name)
start_date = st.date_input("Start Date", value=datetime.today())
duration_days_input = st.number_input("Duration (days)", min_value=1, max_value=30, value=duration_days)

cols = st.columns(len(dose_times))
dose_inputs = []
for i, col in enumerate(cols):
    with col:
        dose_inputs.append(st.time_input(f"Dose {i+1} Time", value=dose_times[i]))

desc_text = {
    "English": f"Take your {med_name_input}",
    "Te Reo Māori": f"Tangohia tō {med_name_input}",
    "Samoan": f"Inu lau {med_name_input}",
    "Mandarin": f"服用 {med_name_input}"
}.get(language, f"Take your {med_name_input}")

def create_event(start_dt, minutes, repeat_count, title, description):
    start_str = start_dt.strftime("%Y%m%dT%H%M%S")
    end_str = (start_dt + timedelta(minutes=minutes)).strftime("%Y%m%dT%H%M%S")
    return f"""BEGIN:VEVENT
SUMMARY:{title}
DTSTART;TZID=Pacific/Auckland:{start_str}
DTEND;TZID=Pacific/Auckland:{end_str}
RRULE:FREQ=DAILY;COUNT={repeat_count}
DESCRIPTION:{description}
END:VEVENT
"""

def build_ics():
    calendar = "BEGIN:VCALENDAR\nVERSION:2.0\n"
    for t in dose_inputs:
        dt_start = datetime.combine(start_date, t)
        calendar += create_event(dt_start, 10, duration_days_input, f"Take {med_name_input}", desc_text)
    calendar += "END:VCALENDAR"
    return calendar

ics_data = build_ics()

st.download_button(
    label="📅 Download Pill Reminder (.ics)",
    data=ics_data,
    file_name=f"{med_name_input.replace(' ', '_')}_reminder.ics",
    mime="text/calendar"
)

          

st.markdown("</div>", unsafe_allow_html=True)

# Disclaimer
st.markdown(f"""
<div style='text-align: center; color: grey; font-size: 0.9em; margin-top: 40px;'>
{L["disclaimer"]}
</div>
""", unsafe_allow_html=True)

# Privacy
with st.expander(L["privacy_title"]):
    st.markdown(L["privacy"])

# FAQ content in multiple languages
faq_sections = {
    "English": """
### ❓ Frequently Asked Questions (FAQ)

#### 💊 About Pill-AI
**What is Pill-AI?**  
Pill-AI is a friendly chatbot that helps New Zealanders understand their medicines.  
**Who is it for?**  
Everyday Kiwis, especially those who:  
– Struggle with medical language  
– Are visually impaired  
– Prefer simpler explanations  
– Want quick answers on their phone  
**Is it free?**  
Yes.

#### 📚 Where the Info Comes From
**Where does Pill-AI get its answers?**  
From Medsafe Consumer Medicine Information (CMI) leaflets.  
**Can I trust it?**  
Yes, but always check with a health professional too.

#### 🗨️ Using Pill-AI
**What can I ask?**  
– "What is cetirizine for?"  
– "Can I take ibuprofen with food?"  
**Does it give medical advice?**  
No. It only explains medicine info — it doesn’t diagnose or prescribe.  
**Can I upload a prescription?**  
Coming soon.

#### 🌐 Languages
**What languages are supported?**  
English, Te Reo Māori, Samoan, Mandarin.  
**Are the translations perfect?**  
Not always — they use AI. Ask a health worker if unsure.

#### 🔐 Privacy and Safety
**Is my data private?**  
Yes. Questions aren't stored.  
**Is this an emergency service?**  
No. Call 111 if it’s urgent.

#### 🧪 Feedback and Credits
**Can I help improve Pill-AI?**  
Yes — especially if you speak Te Reo or Samoan.  
**Who made this?**  
It was developed in Aotearoa NZ using Medsafe info to make medicine info more accessible.
""",
    "Te Reo Māori": """
### ❓ He Pātai Auau

#### 💊 Mō Pill-AI
**He aha a Pill-AI?**  
He kaiawhina ā-ipurangi hei whakamārama i ngā rongoā.  
**Mō wai tēnei?**  
Mō ngā tāngata katoa — otirā te hunga:  
– E uaua ana ki te mārama ki ngā kupu hauora  
– Kua ngoikore te kite  
– E hiahia ana i ngā whakamārama māmā  
**He utu āwhina?**  
Kāo – he kore utu.

#### 📚 Nō hea ngā pārongo?
**Kei hea e tiki ana a Pill-AI i ngā kōrero?**  
Mai i ngā tuhinga CMI a Medsafe.  
**Ka taea te whakawhirinaki?**  
Āe – engari me ui tonu ki tō rata, ki te kaiwhakarato hauora hoki.

#### 🗨️ Te whakamahi i a Pill-AI
**He aha ngā pātai ka taea?**  
– "He aha te mahi a cetirizine?"  
– "Ka taea te kai me te ibuprofen?"  
**Ka tuku tohutohu hauora?**  
Kāo – he whakamārama anake, kāore e tuku tohutohu, āta wānanga rānei.  
**Ka taea te tuku whakaahua o te rongoā?**  
Ā tōna wā.

#### 🌐 Ngā Reo
**Ngā reo tautoko:**  
Te Reo Māori, Ingarihi, Gagana Sāmoa, Mandarin.  
**He tika ngā whakamāoritanga?**  
Kāore i te tino tika i ngā wā katoa – whakamahia mā te āta whakaaro.

#### 🔐 Te Tūmataiti me te Haumaru
**Ka tiakina taku raraunga?**  
Āe – kāore mātou e penapena i ngā pātai.  
**He ratonga ohotata tēnei?**  
Kāo – waea atu ki te 111 mēnā he ohotata.

#### 🧪 Urupare
**Ka taea te tuku urupare?**  
Āe – āwhina mai mēnā e mōhio ana koe ki Te Reo.  
**Nā wai i waihanga?**  
Nā tētahi kairangahau i Aotearoa hei āwhina i te marea.
""",
    "Samoan": """
### ❓ Fesili e masani ona fesiligia

#### 💊 E uiga i Pill-AI
**O le ā le Pill-AI?**  
O se fesoasoani fa'akomepiuta e fesoasoani ia te oe e malamalama i fualaau.  
**Mo ai?**  
Mo tagata uma — aemaise i ē:  
– E faigatā ona malamalama i le gagana fa'afoma'i  
– E le lelei le vaai  
– E mana'o i se fa'amatalaga faigofie  
**E totogi?**  
Leai – e fua fua.

#### 📚 O fea mai ai fa'amatalaga?
**O fea e maua mai ai fa'amatalaga a Pill-AI?**  
Mai Medsafe – CMI pepa.  
**E mafai ona fa'atuatuaina?**  
Ioe – ae fesili pea i lau foma'i.

#### 🗨️ Fa'aoga
**O le ā e mafai ona ou fesili ai?**  
– "O le ā le cetirizine?"  
– "E mafai ona inu ibuprofen ma le taumafataga?"  
**E foa'i fautuaga fa'afoma'i?**  
Leai – e fa'amatala atu na'o le fa'amatalaga.  
**E mafai ona ou lafoina se vaila'au pepa?**  
O lo'o galue iai.

#### 🌐 Gagana
**O ā gagana e avanoa?**  
Gagana Peretania, Te Reo Māori, Gagana Samoa, Mandarin.  
**E atoatoa faaliliuga?**  
E le atoatoa – fa'amalie atu.

#### 🔐 Fa'alilolilo ma le Saogalemu
**E fa'apefea ona puipuia a'u fa'amatalaga?**  
E le teuina au fesili.  
**O se auaunaga fa'afuase'i?**  
Leai – vala'au le 111 pe a manaomia.

#### 🧪 Fesoasoani
**E mafai ona ou fesoasoani e fa'aleleia?**  
Ioe – aemaise pe a mafai ona e fesoasoani i le gagana.  
**O ai na faia?**  
Na fausia i Niu Sila mo tagata Niu Sila.
""",
    "Mandarin": """
### ❓ 常见问题 (FAQ)

#### 💊 关于 Pill-AI
**什么是 Pill-AI？**  
Pill-AI 是一个帮助新西兰人了解药品信息的聊天机器人。  
**适合谁使用？**  
适合所有人，特别是：  
– 难以理解医疗术语的人  
– 视力不好的人  
– 想要简明易懂解释的人  
**是免费的吗？**  
是的，完全免费。

#### 📚 信息来源
**Pill-AI 的信息来源是哪里？**  
来自新西兰 Medsafe 的 CMI（药品说明书）。  
**这些信息可靠吗？**  
可靠，但建议同时咨询医生或药剂师。

#### 🗨️ 如何使用 Pill-AI
**我可以问什么？**  
– “Cetirizine 有什么作用？”  
– “饭前可以吃布洛芬吗？”  
**会提供医疗建议吗？**  
不会，它只解释药品信息，不提供诊断或处方。  
**可以上传处方照片吗？**  
即将推出。

#### 🌐 支持的语言
**支持哪些语言？**  
英语、毛利语、萨摩亚语、中文。  
**翻译准确吗？**  
并非完全准确，重要问题请咨询专业人士。

#### 🔐 隐私与安全
**我的问题会被记录吗？**  
不会，问题不会被存储。  
**这是不是紧急服务？**  
不是。如遇紧急情况，请拨打 111。

#### 🧪 意见与反馈
**我可以帮助改进吗？**  
可以，尤其是懂双语的用户。  
**这个工具是谁做的？**  
由新西兰团队开发，目的是让药品信息更易懂。
"""
}

# Add FAQ section using language-based selection
faq_title = {
    "English": "❓ FAQ – Click to expand",
    "Te Reo Māori": "❓ He Pātai Auau – Pāwhiritia kia kite",
    "Samoan": "❓ Fesili masani – Kiliki e faitau",
    "Mandarin": "❓ 常见问题 – 点击展开"
}.get(language, "❓ FAQ – Click to expand")

with st.expander(faq_title):
    st.markdown(faq_sections.get(language, faq_sections["English"]))
