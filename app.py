import time, re, io
import subprocess
import streamlit as st
from langchain_ollama import OllamaLLM
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit


def generate_pdf():
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    y = height - 40  # Start position for text
    max_width = width - 80  # Margin for text wrapping

    c.setFont("Helvetica-Bold", 16)
    header_text = "Conversation History"
    text_width = c.stringWidth(header_text, "Helvetica-Bold", 16)
    c.drawString((width - text_width) / 2, height - 40, header_text)

    y -= 30  # Adjust position after header
    c.setFont("Helvetica", 12)

    for msg in st.session_state.messages:
        role = "User" if msg["role"] == "user" else "LLM"
        text = f"{role}: {msg['content']}"

        # Separate user questions with a line
        if msg["role"] == "user":
            y -= 10
            c.setStrokeColorRGB(0, 0, 0)
            c.line(40, y, width - 40, y)
            y -= 20  

        # Wrap text within max_width
        wrapped_lines = simpleSplit(text, c._fontname, c._fontsize, max_width)

        for line in wrapped_lines:
            c.drawString(40, y, line)
            y -= 20
            
            # Handle page breaks
            if y < 40:
                c.showPage()
                c.setFont("Helvetica", 12)
                y = height - 40  # Reset position after new page

    c.save()
    buffer.seek(0)
    return buffer

def get_available_models():
    """Fetches the installed Ollama models, excluding 'NAME' and models containing 'embed'."""
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=True)
        models = [
            line.split(" ")[0] for line in result.stdout.strip().split("\n")
            if line and "NAME" not in line and "embed" not in line.lower()
        ]
        return models
    except subprocess.CalledProcessError as e:
        print(f"Error fetching models: {e}")
        return []

def format_time(response_time):
    minutes = response_time // 60
    seconds = response_time % 60
    return f"{int(minutes)}m {int(seconds)}s" if minutes else f"Time: {int(seconds)}s"

def remove_tags(text):
    return re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

# Fetch available models
available_models = get_available_models()
if not available_models:
    st.error("No installed Ollama models found. Please install one using `ollama pull <model_name>`.")

# Streamlit page configuration
st.set_page_config(page_title="Chat with Ollama", page_icon="🤖")
st.markdown("#### 🗨️ Chat with Ollama")

with st.sidebar:
    st.title("Settings :")

    # User selects the model to use
    selected_model = st.selectbox("Select an Ollama model:", available_models, index=0)

    # Button to download PDF
    if st.button("Download Chat as PDF"):
        pdf_buffer = generate_pdf()
        st.download_button(
            label="Download",
            data=pdf_buffer,
            file_name="chat_history.pdf",
            mime="application/pdf"
        )

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# Store the selected model in session state
if "ollama_model" not in st.session_state:
    st.session_state["ollama_model"] = selected_model

if selected_model != st.session_state.get("ollama_model"):
    st.session_state["ollama_model"] = selected_model
    st.session_state.messages = []  # Clear messages when changing model
    st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

ollama_llm = OllamaLLM(model=st.session_state["ollama_model"])

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask Me!"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking..."):
                token_count = ollama_llm.get_num_tokens(prompt)
                start_time = time.time()

                response_placeholder = st.empty() 
                streamed_response = ""

                for chunk in ollama_llm.stream(prompt):  # Stream response
                    streamed_response += chunk
                    response_placeholder.markdown(streamed_response) 

                response_time = time.time() - start_time

                response = f"""
                    {remove_tags(streamed_response)}
                    \n---
                    Token Count: {token_count} | Response Time: {format_time(response_time)}"""

                st.markdown(f"""
                    \n---
                    Token Count: {token_count} | Response Time: {format_time(response_time)}""")

            # Display and store assistant response
            st.session_state.messages.append({"role": "assistant", "content": response})

        except Exception as e:
            st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})
            st.rerun()
