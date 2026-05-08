import streamlit as st
from agent import handle_query
from streamlit_mic_recorder import mic_recorder
# ---------------------------------
# PAGE CONFIG
# ---------------------------------

st.set_page_config(
    page_title="Jarvis AI Assistant",
    page_icon="🤖",
    layout="wide"
)
# ---------------------------------
# LOAD CSS
# ---------------------------------

with open("styles/style.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ---------------------------------
# SESSION STATE
# ---------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------------------------
# HEADER
# ---------------------------------

st.markdown('<div class="title">JARVIS AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Voice-Controlled AI Assistant</div>',
    unsafe_allow_html=True
)
# ---------------------------------
# TOP STATUS CARDS
# ---------------------------------

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        '''
        <div class="status-card">
            <h3>🧠 Model</h3>
            <p>LLaMA3 + Mistral</p>
        </div>
        ''',
        unsafe_allow_html=True
    )
with col2:
    st.markdown(
        '''
        <div class="status-card">
            <h3>🎤 Voice</h3>
            <p>Faster-Whisper</p>
        </div>
        ''',
        unsafe_allow_html=True
    )
with col3:
    st.markdown(
        '''
        <div class="status-card">
            <h3>⚡ Status</h3>
            <p>Online</p>
        </div>
        ''',
        unsafe_allow_html=True
    )
# ---------------------------------
# VOICE ORB
# ---------------------------------

st.markdown(
    '''
    <div class="orb-container">
        <div class="orb"></div>
    </div>
    ''',
    unsafe_allow_html=True
)
# ---------------------------------
# USER INPUT
# ---------------------------------

user_input = st.chat_input("Give a command to Jarvis...")


# ---------------------------------
# HANDLE INPUT
# ---------------------------------
if user_input:

    # save user msg
    st.session_state.messages.append(("user", user_input))

    # process response
    response = handle_query(user_input)

    # save bot msg
    st.session_state.messages.append(("bot", response))
# ---------------------------------
# CHAT DISPLAY
# ---------------------------------

st.markdown('<div class="chat-box">', unsafe_allow_html=True)

for role, msg in st.session_state.messages:

    if role == "user":
        st.markdown(
            f'<div class="user-msg">🧑 You: {msg}</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="bot-msg">🤖 Jarvis: {msg}</div>',
            unsafe_allow_html=True
        )

st.markdown('</div>', unsafe_allow_html=True)
